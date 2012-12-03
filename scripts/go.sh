#!/bin/bash

# Convenience script which sets up Linux test environment
pids=""

function quit() {
  if [ -n "$pids" ]
  then
    echo ""
    echo "Killing child processes $pids"
    ps $pids
    kill -SIGINT $pids
  fi
  exit 0
}

trap quit SIGINT

XTERM_ARGS="-fa 'Mono' -fs 10"

curl -v localhost:8080 2>/dev/null
if [ $? -ne 0 ]
then
  xterm $XTERM_ARGS -geometry 120x32+0+1000 -e scripts/run.sh &
fi

xterm $XTERM_ARGS -geometry 120x15+1040+1000 -e scripts/test.sh --browsers= &
pids="$$ $pids"

xterm $XTERM_ARGS -geometry 120x15+1040+1290 -e scripts/e2e-test.sh --browsers= &
pids="$$ $pids"

sleep 1
CHROME_ARGS="--no-default-browser-check --no-first-run"

google-chrome $CHROME_ARGS \
  --window-size=520,300 \
  --window-position=100,50 \
  --user-data-dir=.chrome-test \
  http://localhost:6060/ &
pids="$$ $pids"


google-chrome $CHROME_ARGS \
  --window-size=520,300 \
  --window-position=100,250 \
  --user-data-dir=.chrome-e2e \
  http://localhost:7070/testacular/ &
pids="$$ $pids"

while [ true ]
do
  sleep 1000
done
