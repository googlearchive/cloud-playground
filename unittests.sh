#!/bin/bash
#
set -uex

APPCFG=$(which appcfg.py)
while [ -L $APPCFG ]
do
  APPCFG=$(readlink $APPCFG)
done

SDK_HOME=$(dirname $APPCFG)

PYTHONPATH=$PYTHONPATH:$SDK_HOME python run_tests.py $*
