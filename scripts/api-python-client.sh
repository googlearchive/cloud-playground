#!/bin/bash
#

# This script ensures that we have a copy of the Google API Client library

set -ue

DOWNLOAD_BASE_URL=https://google-api-python-client.googlecode.com/files
DOWNLOAD_FILENAME=google-api-python-client-gae-1.2.zip
EXTRACT_DIRECTORY=api-python-client

SCRIPT_DIR=$( dirname $0)
ROOT_DIR=$( dirname $SCRIPT_DIR)


if [ ! -d $ROOT_DIR/$EXTRACT_DIRECTORY ]
then
  echo -e "\n*** Downloading $DOWNLOAD_BASE_URL/$DOWNLOAD_FILENAME ***\n"
  wget -q $DOWNLOAD_BASE_URL/$DOWNLOAD_FILENAME -O /tmp/$DOWNLOAD_FILENAME || exit
  echo "Done"

  echo -e "\n*** Extracting /tmp/$DOWNLOAD_FILENAME into $ROOT_DIR/$EXTRACT_DIRECTORY ***\n"
  #mkdir $ROOT_DIR/$EXTRACT_DIRECTORY
  unzip -q /tmp/$DOWNLOAD_FILENAME -d $ROOT_DIR/$EXTRACT_DIRECTORY
  echo "Done"
fi
