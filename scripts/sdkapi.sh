#!/bin/bash
#

# This script copies a few files from google.appengine.api.appinfo from the
# local SDK into a directory named 'sdkapi' since the appinfo package is
# currently unavailable in the production App Engine environment

set -ue

APPCFG=$(which appcfg.py) \
  || (echo "ERROR: appcfg.py must be in your PATH"; exit 1)
while [ -L $APPCFG ]
do
  APPCFG=$(readlink $APPCFG)
done

SDK_HOME=$(dirname $APPCFG)

SRC=$SDK_HOME/google/appengine/api
DST=sdkapi

echo -e "\n*** Stuffing $SRC/ into $DST/ ***\n"

API_MODULES="\
__init__ \
appinfo \
appinfo_errors \
backendinfo \
pagespeedinfo \
validation \
yaml_builder \
yaml_errors \
yaml_listener \
yaml_object"

rm -rf $DST
mkdir -p $DST

for m in $API_MODULES
do
  s=$SRC/$m.py
  d=$DST/$m.py
  echo "- google.appengine.api.$m"
  cat $s \
  | sed -e 's#google.appengine.api#sdkapi#g' \
  | sed -e 's#google/appengine/api#sdkapi#g' \
  > $d
done

echo -e "Done.\n"
