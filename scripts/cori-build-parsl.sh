#!/bin/bash -ex

# requires parsl source checkout in $(pwd)/parsl/

#module load python/3.6-anaconda-5.2
#source /global/common/software/lsst/common/miniconda/setup_current_python.sh
export PATH=/global/homes/d/descim/miniconda3/bin:$PATH

# delete old conda environment

rm -rf ~/.conda/envs/parsl-imsim-nov2018

conda create -n parsl-imsim-nov2018 -y
source activate parsl-imsim-nov2018

conda install mpi4py -y

pushd parsl
pip install .
popd
