'use strict';

/* Services */

angular.module('playgroundApp.services', [])

// TODO: test
.factory('IframedDetector', function($location, $rootScope, $window) {
  $rootScope.iframed = $location.search()['iframed'] ||
                       $window.top != $window.self;
  return {};
})

// TODO: test
.factory('Alert', function() {

  var alert_list = [];

  var is_cookie_problem = false;

  var Alert = {
    alert_list: alert_list,

    handle_exception: function(exception, cause) {
      var msg = '' + exception;
      if (cause) {
        msg += ' caused by ' + cause;
      }
      alert_list.push({type: 'error', icon: 'icon-exclamation-sign', msg: msg});
    },

    note: function(msg) {
      alert_list.push({icon: 'icon-hand-right', msg: msg});
    },

    info: function(msg) {
      alert_list.push({type: 'info', icon: 'icon-info-sign', msg: msg});
    },

    success: function(msg) {
      alert_list.push({type: 'success', icon: 'icon-ok', msg: msg});
    },

    error: function(msg) {
      alert_list.push({type: 'error', icon: 'icon-exclamation-sign', msg: msg});
    },

    alerts: function() {
      return alert_list;
    },

    remove_alert: function(idx) {
      alert_list.splice(idx, 1);
    },

    cookie_problem: function(problem) {
      if (problem == undefined) {
        return is_cookie_problem;
      }
      is_cookie_problem = problem;
    },
  };

  return Alert;

})

// TODO: improve upon flushDoSerial(); allow one step to be executed at a time
.factory('DoSerial', function($timeout, $log, $exceptionHandler, Alert) {

  var work_items = [];
  var pending_promise;

  var on_promised_satisfied_success = function() {
    pending_promise = undefined;
    maybe_next();
  };

  var on_promised_satisfied_error = function(rejection) {
    Alert.error('Execution step failed\n:' + angular.toJson(rejection));
    pending_promise = undefined;
    maybe_next();
  };

  var maybe_next = function() {
    if (pending_promise) return;
    if (!work_items.length) return;

    var result;
    try {
      result = work_items.shift()();
    } catch (err) {
      $exceptionHandler(err);
    }

    if (result && result.then) {
      pending_promise = result.then(on_promised_satisfied_success,
                                    on_promised_satisfied_error);
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

.factory('playgroundHttpInterceptor', function($q, $log, $window, Alert) {
  return function(promise) {
    return promise.then(function(response) {
      return response;
    }, function(err) {
      // TODO: use 'return $q.reject(err)' instead of throwing errors,
      // while still showing errors in Alert service and $log
      if (err instanceof Error) {
        throw err;
      } else if (err.headers('X-Cloud-Playground-Error')) {
        if (err.status == 401) {
          Alert.cookie_problem(true);
        }
        throw 'Cloud Playground error:\n' + err.data;
      } else {
        // err properties: data, status, headers, config
        throw 'HTTP ERROR ' + err.status + ': ' +
              err.config.method + ' ' + err.config.url + '\n' +
              err.data;
      }
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

  // Exponential backoff service.

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

.factory('WindowService', function($window) {
  var WindowService = {
    'reload': function() {
      // TODO: don't access 'document' directly
      document.body.scrollTop = 0;
      $window.location.reload();
    },
    'open': function(url, name, specs, replace) {
      $window.open(url, name, specs, replace);
    },
  };
  return WindowService;
})

// Prompt service. Used only for prompts that do not require text input.
// TODO: test
.factory('ConfirmDialog', function($dialog) {
  return function(title, msg, okButtonText, okButtonClass, callback) {
    // TODO: autofocus primary button
    var btns = [{result: false, label: 'Cancel'},
                {result: true, label: okButtonText,
                 cssClass: okButtonClass}];
    $dialog.messageBox(title, msg, btns)
    .open()
    .then(function(result) {
      if (result) {
        callback();
      }
    });
  }
});
