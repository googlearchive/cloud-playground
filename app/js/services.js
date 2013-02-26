'use strict';

/* Services */

angular.module('playgroundApp.services', [])

// TODO: test
.factory('Alert', function() {

  var alert_list = [];

  var Alert = {
    alert_list: alert_list,

    handle_exception: function(exception, cause) {
      var msg = '' + exception;
      if (cause) {
        msg += ' caused by ' + cause;
      }
      alert_list.push({type: 'error', msg: msg});
    },

    note: function(msg) {
      alert_list.push({msg: msg});
    },

    info: function(msg) {
      alert_list.push({type: 'info', msg: msg});
    },

    success: function(msg) {
      alert_list.push({type: 'success', msg: msg});
    },

    error: function(msg) {
      alert_list.push({type: 'error', msg: msg});
    },

    alerts: function() {
      return alert_list;
    },

    remove_alert: function(idx) {
      alert_list.splice(idx, 1);
    },
  };

  Alert.note('Note: This is a shared public playground.' +
             ' Anyone can read, modify or delete your projects,'+
             ' files and data at any time. Your private source'+
             ' code and data are not safe here.');

  return Alert;

})

// TODO: test
/* temporarily commented out due to failing tests
// TODO: extend built-in $exceptionHandler rather than reimplementing our own
.factory('$exceptionHandler', function($log, Alert) {

  // borrowed from app/lib/angular/angular.js
  function formatError(arg) {
    if (arg instanceof Error) {
      if (arg.stack) {
        arg = (arg.message && arg.stack.indexOf(arg.message) === -1)
            ? 'Error: ' + arg.message + '\n' + arg.stack
            : arg.stack;
      } else if (arg.sourceURL) {
        arg = arg.message + '\n' + arg.sourceURL + ':' + arg.line;
      }
    }
    return arg;
  }

  return function(exception, cause) {
    $log.error.apply($log, arguments);

    // borrowed from app/lib/angular/angular.js
    var args = [];
    angular.forEach(arguments, function(arg) {
      args.push(formatError(arg));
    });

    var msg = args[0];
    if (args.length > 1) {
      msg += '\ncaused by:\n' + args[1];
    }

    Alert.error(msg);
  };

})
*/

// TODO: improve upon flushDoSerial(); allow one step to be executed at a time
.factory('DoSerial', function($timeout, $log, $exceptionHandler) {

  var work_items = [];
  var pending_promise;

  var on_promised_satisfied = function() {
    pending_promise = undefined;
    maybe_next();
  }

  var maybe_next = function() {
    if (pending_promise) return;
    if (!work_items.length) return;

    var result;
    try {
      result = work_items.shift()();
    } catch(err) {
      $exceptionHandler(err);
    }

    if (result && result.then) {
      pending_promise = result.then(on_promised_satisfied,
                                    on_promised_satisfied);
    } else {
      maybe_next();
    }
  };

  // TODO: rename to 'Queue'
  var DoSerial = {
    // yield execution until next tick from the event loop
    tick: function() {
      return this.then(function() {
        return $timeout(angular.noop);
      });
    },
    // schedule action to perform next
    then: function(func) {
      work_items.push(func);
      maybe_next();
      return DoSerial;
    }
  };

  return DoSerial;
})

.factory('playgroundHttpInterceptor', function($q, $log, $window) {
  return function(promise) {
    return promise.then(function(response) {
      return response;
    }, function(err) {
      if (err instanceof Error) {
        $log.error(err);
      } else if (err.headers('X-Cloud-Playground-Error')) {
        $log.error('Error:\n' + err.data);
      } else {
        $log.error('HTTP ERROR', err);
      }
      return $q.reject(err);
    });
  };
})

// TODO: if want to focus() element create Focus service
.factory('DomElementById', function($window) {
  return function(id) {
    return $window.document.getElementById(id);
  };
})

// TODO: move output iframe into directive with a template.html
// TODO: get rid of other uses
.factory('WrappedElementById', function(DomElementById) {
  return function(id) {
    return angular.element(DomElementById(id));
  };
})

// TODO: test
// TODO: DETERMINE if there's a better way
.factory('Backoff', function($timeout) {

  "Exponential backoff service."

  var INIITAL_BACKOFF_MS = 1000;
  var backoff_ms;
  var timer = undefined;

  var Backoff = {
    reset: function() {
      backoff_ms = INIITAL_BACKOFF_MS;
    },
    backoff: function() {
      backoff_ms = Math.min(120 * 1000, (backoff_ms || 1000) * 2);
      return backoff_ms;
    },
    schedule: function(func) {
      if (timer) {
        return;
      }
      timer = $timeout(function() {
        timer = undefined;
        func();
      }, backoff_ms);
    },
  };

  Backoff.reset();
  return Backoff;
})
