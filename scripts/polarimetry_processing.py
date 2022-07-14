# helper functions for naming output product
def convert_abs_rel_orbit(abs_orbit, satellite):
    if satellite == "S1A":
        rel_orbit = (int(abs_orbit) - 73) % 175 + 1
    if satellite == "S1B":
        rel_orbit = (int(abs_orbit) - 27) % 175 + 1
    return rel_orbit


def name_polar_prod(file):
    time = os.path.split(file)[-1].split("_")[5]
    sat = os.path.split(file)[-1].split("_")[0]
    abs_orbit = os.path.split(file)[-1].split("_")[7]
    rel_orbit = convert_abs_rel_orbit(abs_orbit, sat)
    name = f"pol_H_a_{rel_orbit}_{time}"
    return name


# define workflow for coherence calculation
def polarimetry_processing(file, out_dir, aoi_wkt, crs):
    # read product
    read = snappy.ProductIO.readProduct(file)
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
            split = snappy.GPF.createProduct("TOPSAR-Split", params, read)
            # apply orbit files
            params = snappy.HashMap()
            params.put("orbitType", "Sentinel Precise (Auto Download)")
            apply_orbit = snappy.GPF.createProduct("Apply-Orbit-File", params, split)
            # calibration
            params = snappy.HashMap()
            params.put("outputImageInComplex", True)
            params.put(
                "sourceBands",
                f"i_{subswath}_VV,q_{subswath}_VV,i_{subswath}_VH,q_{subswath}_VH",
            )
            params.put("selectedPolarisation", "VH,VV")
            params.put("outputImageScaleInDb", False)
            calibrated = snappy.GPF.createProduct("Calibration", params, apply_orbit)
            # debursting
            params = snappy.HashMap()
            params.put(
                "selectedPolarisations", ",".join(list(calibrated.getBandNames()))
            )
            deburst = snappy.GPF.createProduct("TOPSAR-Deburst", params, calibrated)
            # store results for all subswaths
            aoi_subswaths_results[f"deburst_{subswath}"] = deburst
        except RuntimeError as e:
            pass
    if len(aoi_subswaths_results):
        if len(aoi_subswaths_results) > 1:
            # merging subswaths
            params = snappy.HashMap()
            params.put("selectedPolarisations", ",".join(list(deburst.getBandNames())))
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
        # generate pol matrix
        params = snappy.HashMap()
        params.put("matrix", "C2")
        pol_matrix = snappy.GPF.createProduct("Polarimetric-Matrices", params, subset)
        # multilooking
        params = snappy.HashMap()
        params.put("nAzLooks", 1)
        params.put("nRgLooks", 4)
        params.put("sourceBands", ",".join(list(pol_matrix.getBandNames())))
        multilooked = snappy.GPF.createProduct("Multilook", params, pol_matrix)
        # perform pol decomposition
        params = snappy.HashMap()
        params.put("decomposition", "H-Alpha Dual Pol Decomposition")
        params.put("outputHAAlpha", True)
        params.put("outputHuynenParamSet0", False)
        pol_decomp = snappy.GPF.createProduct(
            "Polarimetric-Decomposition", params, multilooked
        )
        # terrain correction
        proj = CRS.from_epsg(crs).to_wkt(WktVersion.WKT1_GDAL)
        params = snappy.HashMap()
        params.put("imgResamplingMethod", "NEAREST_NEIGHBOUR")
        params.put("pixelSpacingInMeter", 10.0)
        params.put("mapProjection", proj)
        params.put("nodataValueAtSea", False)
        params.put("saveSelectedSourceBand", True)
        terrain_corrected = snappy.GPF.createProduct(
            "Terrain-Correction", params, pol_decomp
        )
        # write product
        name_intensity_product = name_polar_prod(file)
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
        description="Performing H-a-dual pol decomposition"
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
    polarimetry_processing(file, out_dir, aoi_wkt, crs)
