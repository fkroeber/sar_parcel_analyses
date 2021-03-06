# some notes on the processing workflow

# conversion to db not part of the processing workflow - to enable averaging in the linear intensity domain
# thermal noise removal doesn't work on subswath in SNAP (-> bug), needs to be executed on all swaths


# helper functions for naming output product
def convert_abs_rel_orbit(abs_orbit, satellite):
    if satellite == "S1A":
        rel_orbit = (int(abs_orbit) - 73) % 175 + 1
    if satellite == "S1B":
        rel_orbit = (int(abs_orbit) - 27) % 175 + 1
    return rel_orbit


def name_gamma_prod(file):
    time = os.path.split(file)[-1].split("_")[5]
    sat = os.path.split(file)[-1].split("_")[0]
    abs_orbit = os.path.split(file)[-1].split("_")[7]
    rel_orbit = convert_abs_rel_orbit(abs_orbit, sat)
    name = f"gamma_VV_VH_{rel_orbit}_{time}"
    return name


# define workflow for coherence calculation
def intensity_processing(file, out_dir, aoi_wkt, crs):
    # read product
    read = snappy.ProductIO.readProduct(file)
    # apply orbit files
    params = snappy.HashMap()
    params.put("orbitType", "Sentinel Precise (Auto Download)")
    apply_orbit = snappy.GPF.createProduct("Apply-Orbit-File", params, read)
    # thermal noise removal
    params = snappy.HashMap()
    params.put("selectedPolarisations", "VV,VH")
    thermal_noise = snappy.GPF.createProduct("ThermalNoiseRemoval", params, apply_orbit)
    # subset to aoi-covering sub-swaths & bursts
    with open(aoi_wkt, "r") as f:
        aoi_wkt = f.read()
    aoi_subswaths_results = {}
    for subswath in ["IW1", "IW2", "IW3"]:
        try:
            params = snappy.HashMap()
            params.put("selectedPolarisations", "VV,VH")
            params.put("subswath", subswath)
            params.put("wktAoi", aoi_wkt)
            split = snappy.GPF.createProduct("TOPSAR-Split", params, thermal_noise)
            # calibration
            params = snappy.HashMap()
            params.put("outputSigmaBand", False)
            params.put("outputBetaBand", True)
            params.put(
                "sourceBands", f"Intensity_{subswath}_VV,Intensity_{subswath}_VH"
            )
            params.put("selectedPolarisation", "VH,VV")
            params.put("outputImageScaleInDb", False)
            calibrated = snappy.GPF.createProduct("Calibration", params, split)
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
        proj = CRS.from_epsg(crs).to_wkt(WktVersion.WKT1_GDAL)
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
        name_intensity_product = name_gamma_prod(file)
        out_path = os.path.join(out_dir, name_intensity_product)
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
    # standard imports & argument parsing
    import os
    import sys
    import argparse
    from pyproj import CRS
    from pyproj.enums import WktVersion

    parser = argparse.ArgumentParser(
        description="Converting SLC to gamma0 backscatter intensity"
    )
    parser.add_argument("-s1_file", help="S1 SLC scene path")
    parser.add_argument("-out_dir", help="directory to write product")
    parser.add_argument("-snap_env", help="path to SNAP python env")
    parser.add_argument("-aoi_wkt", help="path to AoI in WKT format")
    parser.add_argument("-crs", help="output projection epsg code")

    args = parser.parse_args()

    file = args.s1_file
    snap_env = args.snap_env
    aoi_wkt = args.aoi_wkt
    out_dir = args.out_dir
    crs = args.crs

    # connection to snappy
    sys.path.append(snap_env)
    import snappy
    import jpy

    # intensity processing
    intensity_processing(file, out_dir, aoi_wkt, crs)
