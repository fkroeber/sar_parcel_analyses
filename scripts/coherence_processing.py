# some notes on the processing workflow

# error handling not optimal - suppression of Java errors would be desirable
# decision to write bands, i.e. VV & VH, together as it saves disk space & speeds up the process
# can be read individually later on, e.g. via rasterio
# also for larger AoI outsourcing the select band operator to a second chain would be necessary anyway
# otherwise java heat space exception followed by nullpointer occurs


# helper functions for naming output product
def convert_abs_rel_orbit(abs_orbit, satellite):
    if satellite == "S1A":
        rel_orbit = (int(abs_orbit) - 73) % 175 + 1
    if satellite == "S1B":
        rel_orbit = (int(abs_orbit) - 27) % 175 + 1
    return rel_orbit


def name_coh_prod(file_1, file_2):
    time_1 = os.path.split(file_1)[-1].split("_")[5]
    time_2 = os.path.split(file_2)[-1].split("_")[5]
    sat = os.path.split(file_1)[-1].split("_")[0]
    abs_orbit = os.path.split(file_1)[-1].split("_")[7]
    rel_orbit = convert_abs_rel_orbit(abs_orbit, sat)
    name = f"coh_VV_VH_{rel_orbit}_{time_1}_{time_2}"
    return name


# workflow for coherence calculation
def coherence_processing(file_1, file_2, aoi_wkt, out_dir, crs):
    # read products
    read_1 = snappy.ProductIO.readProduct(file_1)
    read_2 = snappy.ProductIO.readProduct(file_2)
    print(f"Available bands: {list(read_1.getBandNames())}")
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
        proj = CRS.from_epsg(crs).to_wkt(WktVersion.WKT1_GDAL)
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
        # extract bands (see comment at the top)
        # for pol in ["VV", "VH"]:
        #     params = snappy.HashMap()
        #     params.put("selectedPolarisations", pol)
        #     single_band = snappy.GPF.createProduct(
        #         "BandSelect", params, terrain_corrected
        #     )
        # write product
        name_coh_product = name_coh_prod(file_1, file_2)
        out_path = os.path.join(out_dir, name_coh_product)
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
        description="Calculating coherence for two S1 scenes"
    )
    parser.add_argument("-file_I", help="first S1 scene (reference)")
    parser.add_argument("-file_II", help="second S1 scene (secondary)")
    parser.add_argument("-out_dir", help="directory to write product")
    parser.add_argument("-snap_env", help="path to SNAP python env")
    parser.add_argument("-aoi_wkt", help="path to AoI in WKT format")
    parser.add_argument("-crs", help="output projection epsg code")

    args = parser.parse_args()

    file_1 = args.file_I
    file_2 = args.file_II
    snap_env = args.snap_env
    aoi_wkt = args.aoi_wkt
    out_dir = args.out_dir
    crs = args.crs

    # connection to snappy
    sys.path.append(snap_env)
    import snappy
    import jpy

    # coherence processing
    coherence_processing(file_1, file_2, aoi_wkt, out_dir, crs)
