## How to install/configure Snap python interface

links: 
* https://senbox.atlassian.net/wiki/spaces/SNAP/pages/50855941/Configure+Python+to+use+the+SNAP-Python+snappy+interface
* https://towardsdatascience.com/getting-started-with-snap-toolbox-in-python-89e33594fa04

# step 1: install suitable python version
* install python 3.6
* install & upgrade pip, juypter, ipykernel in base env
* create virtualenv (see bash history)
* in virtual env set: pip install --upgrade prompt-toolkit==2.0.1

# step 2: connect to SNAP
* call snap command line as programme
* snappy-conf "{virtualenv}\Scripts\python.exe" "{virtualenv}\snap\Lib"
* test snap interface 
    + import os
    + sys.path.append('{virtualenv}\\Lib')
    + from snappy import ProductIO
    + testdata_loc = os.path.join(os.path.dirname(snappy.__file__), "testdata", "MER_FRS_L1B_SUBSET.dim")
    + p = ProductIO.readProduct(testdata_loc)
    + list(p.getBandNames())

# step 3: adjust memory settings
* within <snappy-dir> 
    + snappy.ini: adjust java_max_mem: 13G (~80% of RAM)
    + jpyconfig.py: jvm_maxmem = "13G"
+ if necessary also adjust tile chache memory of SNAP installation
    + (C:\Program Files\snap\etc) snap.properties: snap.jai.tileCacheSize = 10000 (~80% of jvm_maxmem)
    + (C:\Program Files\snap\bin) gm.vmoptions: -Xmx12G