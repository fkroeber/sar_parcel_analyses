# establish connection to SNAP & import corresponding
import os
import sys

sys.path.append("C:\\Users\\felix\\.virtualenvs\\snap\\Lib")
import snappy
import jpy

# define workflow for coherence calculation
def intensity_processing(file):
    # read product
    read = snappy.ProductIO.readProduct(file)
    # subset to aoi-covering sub-swaths & bursts
    with open(
        "C://Users/felix/Desktop/Adv_Rs_project/01_data_raw/test_area_processing.txt",
        "r",
    ) as f:
        aoi_wkt = f.read()
    aoi_subswaths_results = {}
    for subswath in ["IW1", "IW2", "IW3"]:
        try:
            params = snappy.HashMap()
            params.put("selectedPolarisations", "VV,VH")
            params.put("subswath", subswath)
            params.put("wktAoi", aoi_wkt)
            split = snappy.GPF.createProduct("TOPSAR-Split", params, read)
            # apply orbit files
            params = snappy.HashMap()
            params.put("orbitType", "Sentinel Precise (Auto Download)")
            apply_orbit = snappy.GPF.createProduct("Apply-Orbit-File", params, split)
            # calibration
            params = snappy.HashMap()
            params.put("outputSigmaBand", False)
            params.put("outputBetaBand", True)
            params.put(
                "sourceBands", f"Intensity_{subswath}_VV,Intensity_{subswath}_VH"
            )
            params.put("selectedPolarisation", "VH,VV")
            params.put("outputImageScaleInDb", False)
            calibrated = snappy.GPF.createProduct("Calibration", params, apply_orbit)
            # terrain flattening
            # more accurate than calibration to gamma0 but also very heavy wrt to processing
            params = snappy.HashMap()
            params.put("sourceBands", f"Beta0_{subswath}_VV,Beta0_{subswath}_VH")
            terrain_flattened = snappy.GPF.createProduct(
                "Terrain-Flattening", params, calibrated
            )
            # debursting
            params = snappy.HashMap()
            params.put("selectedPolarisations", "VV,VH")
            deburst = snappy.GPF.createProduct(
                "TOPSAR-Deburst", params, terrain_flattened
            )
            # store results for all subswaths
            aoi_subswaths_results[f"deburst_{subswath}"] = deburst
        except RuntimeError as e:
            if (
                e
                == "org.esa.snap.core.gpf.OperatorException: wktAOI does not overlap any burst"
            ):
                pass
    if len(aoi_subswaths_results):
        if len(aoi_subswaths_results) > 1:
            # merging subswaths
            params = snappy.HashMap()
            params.put("selectedPolarisations", "VV,VH")
            merge = snappy.GPF.createProduct(
                "TOPSAR-Merge", params, list(aoi_subswaths_results.values())
            )
        else:
            merge = list(aoi_subswaths_results.values())[0]
        # subset to aoi
        params = snappy.HashMap()
        params.put("copyMetadata", True)
        params.put("geoRegion", aoi_wkt)
        subset = snappy.GPF.createProduct("Subset", params, merge)
        # multilooking
        params = snappy.HashMap()
        params.put("nAzLooks", 1)
        params.put("nRgLooks", 4)
        params.put("sourceBands", ",".join(list(subset.getBandNames())))
        multilooked = snappy.GPF.createProduct("Multilook", params, subset)
        # terrain correction
        proj = """
        PROJCS["WGS 84 / UTM zone 33N",GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563,AUTHORITY["EPSG","7030"]],AUTHORITY["EPSG","6326"]],PRIMEM["Greenwich",0,AUTHORITY["EPSG","8901"]],UNIT["degree",0.0174532925199433,AUTHORITY["EPSG","9122"]],AUTHORITY["EPSG","4326"]],PROJECTION["Transverse_Mercator"],PARAMETER["latitude_of_origin",0],PARAMETER["central_meridian",15],PARAMETER["scale_factor",0.9996],PARAMETER["false_easting",500000],PARAMETER["false_northing",0],UNIT["metre",1,AUTHORITY["EPSG","9001"]],AXIS["Easting",EAST],AXIS["Northing",NORTH],AUTHORITY["EPSG","32633"]]
        """
        params = snappy.HashMap()
        params.put("imgResamplingMethod", "NEAREST_NEIGHBOUR")
        params.put("pixelSpacingInMeter", 10.0)
        params.put("mapProjection", proj)
        params.put("nodataValueAtSea", False)
        params.put("saveSelectedSourceBand", True)
        params.put("saveIncidenceAngleFromEllipsoid", True)
        terrain_corrected = snappy.GPF.createProduct(
            "Terrain-Correction", params, multilooked
        )
        # write product
        time = os.path.split(file)[-1].split("_")[5]
        name_intensity_product = f"gamma_VV_VH_angle_{time}"
        out_path = os.path.join(
            "C:/Users/felix/Desktop/Adv_Rs_project/09_temp_playground",
            name_intensity_product,
        )
        incremental = False
        snappy.GPF.writeProduct(
            terrain_corrected,
            snappy.File(out_path),
            "GeoTIFF",
            incremental,
            snappy.ProgressMonitor.NULL,
        )
    else:
        print("--- Warning: AoI covers none of the subswaths! ---")


# conversion to db (only after averaging in intensity domain)
# stacking

# # thermal noise removal (doesnt work in SNAP on subswath)
# params = snappy.HashMap()
# params.put("selectedPolarisations", "VV,VH")
# thermal_noise = snappy.GPF.createProduct(
#     "ThermalNoiseRemoval", params, apply_orbit
# )

if __name__ == "__main__":
    file = sys.argv[1]
    intensity_processing(file)
