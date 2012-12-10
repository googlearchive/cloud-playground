#!/bin/bash

PYTHONPATH=$(dirname $(which dev_appserver.py)) python scripts/run_tests.py
