#!/bin/bash
#
set -uex

./sdkapi.sh

dev_appserver.py --address 0.0.0.0 --skip_sdk_update_check --high_replication . $*
