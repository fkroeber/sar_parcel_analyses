## SAR-based parcel analyses

To the right: Collection of scripts for performing SAR-based analyses on agricultural fields

Synthetic Aperture Radar (SAR) can be used for a variety of intersting applications in the field of remote sensing. Some of the most common SAR-based features comprise the backscatter intensity, polarimetric decomposition parameters and coherence values. Different to achievements in the field of optical data (e.g. Sentinel-2), provisions of ready-to-use data products containing these features are still rare. Apart from backscatter intensities, most of the other features are not provided in cloud-based data cube environments (such as GEE) yet. This repo therefore contains some basic scripts calling the SNAP python interface (snappy) to create these products in an automated manner for a set of downloaded Sentinel-1 scenes and a given AoI.

The scripts for processing are organised as follows:

Independent from that but supporting, ...


These scripts are working on their own and can be used for different purposes. However, they were created and primarily used in the context of field-based analyses (phenology and crop classification). Thus, alongside with the above-mentioned scripts there is a script called "xy.z" reading in the pre-processed data and analysing it subsequently by creating time-series curves and performing classifications using the random forest classifier. 

# Note
* processing requirements (CPU, storage, etc) - tests on larger AoIs not performed, no reliability for that
* performance tests

Visualisation of some outputs/For further information see (blogpost)
...


Progress of preparing scripts
done:
    download_preprocessing
    snap_preprocessing

tbd:
    analyses
    py scripts
