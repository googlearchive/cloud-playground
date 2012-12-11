#!/bin/bash

PYTHONPATH="$(dirname $(which dev_appserver.py)):$PYTHONPATH" \
  python scripts/run_tests.py
