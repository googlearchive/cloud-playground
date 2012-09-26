#!/bin/bash
#
set -ue

./sdkapi.sh

function deploy() {
  echo -e "\n*** Rolling back any pending updates (just in case) ***\n"
  appcfg.py --oauth2 $* rollback .

  echo -e "\n*** DEPLOYING ***\n"
  appcfg.py --oauth2 $* update .
}

if [ $( echo "- A" | egrep -- '-A'\|'--application=' >/dev/null; echo $? ) == 0 ]
then
  deploy $*
else
  appids=$(python -c 'import settings; settings.PrintAppIdsInMap()')
  for appid in $appids
  do
    deploy -A $appid $*
  done
fi
