#!/bin/bash
#
set -ue

VERSION=$(git log -1 --pretty=format:%H)
if [ -n "$(git status --porcelain)" ]
then
  VERSION="dirty-$VERSION"
fi

git status
echo
echo -e "Hit [ENTER] to continue: \c"
read

$(dirname $0)/sdkapi.sh
$(dirname $0)/api-python-client.sh

APPCFG=$(which appcfg.py) \
  || (echo "ERROR: appcfg.py must be in your PATH"; exit 1)
while [ -L $APPCFG ]
do
  APPCFG=$(readlink $APPCFG)
done

BIN_DIR=$(dirname $APPCFG)

if [ "$(basename $BIN_DIR)" == "bin" ]
then
  SDK_HOME=$(dirname $BIN_DIR)
  if [ -d $SDK_HOME/platform/google_appengine ]
  then
    SDK_HOME=$SDK_HOME/platform/google_appengine
  fi
else
  SDK_HOME=$BIN_DIR
fi

function deploy() {
  echo -e "\n*** Rolling back any pending updates (just in case) ***\n"
  appcfg.py --oauth2 $* rollback .

  echo -e "\n*** DEPLOYING ***\n"
  appcfg.py --oauth2 $* update -V $VERSION .

  echo -e "\n*** SETTING DEFAULT VERSION ***\n"
  appcfg.py --oauth2 $* set_default_version -V $VERSION .
}


if [ $( echo "$*" | egrep -- '-A'\|'--application=' >/dev/null; echo $? ) == 0 ]
then
  deploy $*
else
  appids=$(python -c 'import appids; appids.PrintAppIds()')
  for appid in $appids
  do
    deploy -A $appid $*
  done
fi
