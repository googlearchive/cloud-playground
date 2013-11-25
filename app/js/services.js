'use strict';

/* Services */

angular.module('playgroundApp.services', [])

// TODO: test
.factory('$exceptionHandler', function($log, Alert) {

  // borrowed from app/lib/angular/angular.js
  function formatError(arg) {
    if (arg instanceof Error) {
      if (arg.stack) {
        arg = (arg.message && arg.stack.indexOf(arg.message) === -1) ?
          'Error: ' + arg.message + '\n' + arg.stack :
          arg.stack;
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

// TODO: test
.factory('CookieFinder', function($q, $log, $window, $location) {
  var deferred = $q.defer();
  $window.document.cookie = "foo=bar; Path=/";
  if ($window.document.cookie) {
    deferred.resolve($window.document.cookie);
    $window.document.cookie = "foo=bar; Path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT;";
  } else {
    var iframed = $location.search()['iframed'] ||
                  $window.top != $window.self;
    if (iframed) {
      deferred.reject('IFRAMED_NO_COOKIE');
    } else {
      deferred.reject('NO_BROWSER_COOKIE');
    }
  }
  return deferred.promise
  .catch(function(rejection) {
    // track and pass on rejection
    track('cookie_problem', rejection);
    return $q.reject(rejection);
  });
})

// TODO: test
.factory('ConfigService', function($http, $log, $q) {
  return $http.get('/playground/getconfig')
  .then(function(resolved) {
    return {
      config: resolved.data,
    };
  });
})

// TODO: test
.factory('ProjectsFactory', function($http, $log, $q) {
  var projects = [];
  return $http.get('/playground/getprojects')
  .then(function(resolved) {
    angular.forEach(resolved.data, function(project) {
      projects.push(project);
    });
    return {
      projects: projects,

      remove: function(project) {
        for (var i in projects) {
          if (projects[i] == project) {
            projects.splice(i, 1);
            break;
          }
        }
        $http.post('/playground/p/' + encodeURI(project.key) + '/delete')
        .catch(function(rejection) {
          // TODO: handle failure
          $log.log('error deleting project:', rejection);
        });

      },
    };
  });
})

// TODO: test
.factory('Alert', function() {

  var alert_list = [];

  var Alert = {
    alert_list: alert_list,

    clear: function() {
      alert_list = [];
    },

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

.factory('pgHttpInterceptor', function($q, $log, $window, Alert) {
  return {
    'request': function(config) {
      return config || $q.when(config);
    },

   'requestError': function(response) {
      return $q.reject(response);
    },

    'response': function(response) {
      return response || $q.when(response);
    },

   'responseError': function(response) {
      if (response.headers('X-Cloud-Playground-Error')) {
        if (response.status == 401) {
          // TODO: treat this case specially?
        }
      }
      return $q.reject(response);
    }
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
