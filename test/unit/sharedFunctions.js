function flushDoSerial($timeout) {
  "Flush a dummy $timeout to force a tick of the event loop"
  $timeout(function() {});
  $timeout.flush();
}
