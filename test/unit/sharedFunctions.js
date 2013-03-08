function flushDoSerial() {
  // Flush a dummy $timeout to force a tick of the event loop
  inject(function($timeout) {
    $timeout(function() {});
    $timeout.flush();
  });
}
