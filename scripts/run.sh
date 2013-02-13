#!/bin/bash
#
set -uex

$(dirname $0)/sdkapi.sh

devappserver2.py \
  --host 0.0.0.0 \
  --skip_sdk_update_check yes \
  . $*
