#!/bin/bash
#
set -uex

$(dirname $0)/sdkapi.sh

dev_appserver.py --address 0.0.0.0 \
  --skip_sdk_update_check --high_replication --backends . $*
