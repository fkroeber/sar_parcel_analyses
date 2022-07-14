# establish connection to SNAP & import corresponding
import os
import sys

sys.path.append("C:\\Users\\felix\\.virtualenvs\\snap\\Lib")
import snappy
import jpy

# some notes

# preferring to write bands, i.e. VV & VH, together as it saves disk space & speeds up the process
# can be read individually later on, e.g. via rasterio
# also for larger AoI outsourcing the select band operator to a second chain would be necessary anyway
# otherwise java heat space exception followed by nullpointer occurs

# define workflow for coherence calculation
def coherence_processing(file_1, file_2):
    # read products
    read_1 = snappy.ProductIO.readProduct(file_1)
    read_2 = snappy.ProductIO.readProduct(file_2)
    print(f"Available bands: {list(read_1.getBandNames())}")
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
            split_1 = snappy.GPF.createProduct("TOPSAR-Split", params, read_1)
            split_2 = snappy.GPF.createProduct("TOPSAR-Split", params, read_2)
            print(f"Available bands: {list(split_1.getBandNames())}")
            # apply orbit files
            params = snappy.HashMap()
            params.put("orbitType", "Sentinel Precise (Auto Download)")
            apply_orbit_1 = snappy.GPF.createProduct(
                "Apply-Orbit-File", params, split_1
            )
            apply_orbit_2 = snappy.GPF.createProduct(
                "Apply-Orbit-File", params, split_2
            )
            # back-geocoding, i.e. coregistration with subpixel accuracy
            params = snappy.HashMap()
            # params.put("demName", "Copernicus 30m Global DEM")
            coregistered_stack = snappy.GPF.createProduct(
                "Back-Geocoding", params, [apply_orbit_1, apply_orbit_2]
            )
            print(f"Available bands: {list(coregistered_stack.getBandNames())}")
            # coherence calculation
            params = snappy.HashMap()
            params.put("cohWinRg", 11)
            params.put("cohWinAz", 3)
            params.put("squarePixel", True)
            params.put("subtractFlatEarthPhase", True)
            params.put("subtractTopographicPhase", True)
            # params.put("demName", "Copernicus 30m Global DEM")
            coherence = snappy.GPF.createProduct(
                "Coherence", params, coregistered_stack
            )
            print(f"Available bands: {list(coherence.getBandNames())}")
            # debursting
            params = snappy.HashMap()
            params.put("selectedPolarisations", "VV,VH")
            deburst = snappy.GPF.createProduct("TOPSAR-Deburst", params, coherence)
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
            print(f"Available bands: {list(merge.getBandNames())}")
        # subset to aoi
        params = snappy.HashMap()
        params.put("copyMetadata", True)
        params.put("geoRegion", aoi_wkt)
        subset = snappy.GPF.createProduct("Subset", params, merge)
        # terrain correction
        proj = """
        PROJCS["WGS 84 / UTM zone 33N",GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563,AUTHORITY["EPSG","7030"]],AUTHORITY["EPSG","6326"]],PRIMEM["Greenwich",0,AUTHORITY["EPSG","8901"]],UNIT["degree",0.0174532925199433,AUTHORITY["EPSG","9122"]],AUTHORITY["EPSG","4326"]],PROJECTION["Transverse_Mercator"],PARAMETER["latitude_of_origin",0],PARAMETER["central_meridian",15],PARAMETER["scale_factor",0.9996],PARAMETER["false_easting",500000],PARAMETER["false_northing",0],UNIT["metre",1,AUTHORITY["EPSG","9001"]],AXIS["Easting",EAST],AXIS["Northing",NORTH],AUTHORITY["EPSG","32633"]]
        """
        params = snappy.HashMap()
        # params.put("demName", "Copernicus 30m Global DEM")
        params.put("imgResamplingMethod", "NEAREST_NEIGHBOUR")
        params.put("pixelSpacingInMeter", 10.0)
        params.put("mapProjection", proj)
        params.put("nodataValueAtSea", False)
        params.put("saveSelectedSourceBand", True)
        terrain_corrected = snappy.GPF.createProduct(
            "Terrain-Correction", params, subset
        )
        # extract bands (not memory efficient)
        # for pol in ["VV", "VH"]:
        #     params = snappy.HashMap()
        #     params.put("selectedPolarisations", pol)
        #     single_band = snappy.GPF.createProduct(
        #         "BandSelect", params, terrain_corrected
        #     )
        # write product
        time_1 = os.path.split(file_1)[-1].split("_")[5]
        time_2 = os.path.split(file_2)[-1].split("_")[5]
        name_coh_product = f"coh_VV_VH_{time_1}_{time_2}"
        out_path = os.path.join(
            "C:/Users/felix/Desktop/Adv_Rs_project/02_data_processed/coherence",
            name_coh_product,
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


if __name__ == "__main__":
    file_1 = sys.argv[1]
    file_2 = sys.argv[2]
    coherence_processing(file_1, file_2)
