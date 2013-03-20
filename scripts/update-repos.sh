#!/bin/bash
#
set -ue

(
  cd $(dirname $0)/../
  for i in repos/appengine-*-python
  do
    (
      echo
      echo $i
      cd $i
      git pull
    )
  done
)
