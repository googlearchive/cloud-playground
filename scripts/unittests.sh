#!/bin/bash
#
set -ue

APPCFG=$(which appcfg.py) \
  || (echo "ERROR: appcfg.py must be in your PATH"; exit 1)
while [ -L $APPCFG ]
do
  APPCFG=$(readlink $APPCFG)
done

SDK_HOME=$(dirname $APPCFG)

PYTHONPATH=$PYTHONPATH:$SDK_HOME python scripts/run_tests.py $*
