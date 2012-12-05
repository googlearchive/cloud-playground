'use strict';

/* Services */

angular.module('playgroundApp.services', [])

.factory('DoSerial', function($q, $timeout, $log) {

  var deferred = $q.defer();
  deferred.resolve();
  var promise = deferred.promise;

  function promisehack(val) {
    if (val && val.then) {
      return val;
    }
    return val();
  }

  var DoSerial = {
    // yield execution until next tick from the event loop
    tick: function() {
      var d = $q.defer();
      $timeout(function() {
        d.resolve();
      });
      promise = promise.then(function() { return d.promise; });
      return DoSerial;
    },
    // schedule action to perform next
    then: function(func) {
      promise = promise.then(function() {
        return promisehack(func);
      },
      function(err) {
        $log.error('DoSerial encountered', err);
        return promisehack(func);
      });
      // allow chained calls, e.g. DoSerial.then(...).then(...)
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

/*

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

.factory('DomElementById', function($window) {
  return function(id) {
    return $window.document.getElementById(id);
  };
})

.factory('WrappedElementById', function(DomElementById) {
  return function(id) {
    return angular.element(DomElementById(id));
  };
})

.factory('LightBox', function($rootScope) {

  $rootScope.lightboxes = [];

  return {
    lightbox: function(summary, details) {
      $rootScope.lightboxes.push({'summary': summary, 'details': details});
    }
  };

})

.directive('resizer', function(WrappedElementById) {
  var downx, downy, isdown, initialheight, elem;
  var dragDiv = WrappedElementById('drag-div');

  function movefunc(evt) {
    if (!isdown) {
      return;
    }
    var newheight = initialheight + (evt.pageY - downy);
    elem.css('height', newheight + 'px');
  };

  function upfunc(evt) {
    isdown = false;
    dragDiv.addClass('hidden');
    dragDiv.unbind('mousemove', movefunc);
    dragDiv.unbind('mouseup', upfunc);
  };

  return function(scope, element, attr) {
    element.css({
      cursor: 'move',
      borderTop: '4px solid #fff',
      borderBottom: '4px solid #fff',
      backgroundColor: '#eee',
      padding: '2px',
    });
    element.bind('mousedown', function(evt) {
      evt.preventDefault();
      isdown = true;
      downx = evt.pageX;
      downy = evt.pageY;
      elem = WrappedElementById(attr.resizer);
      initialheight = elem.prop('offsetHeight');
      dragDiv.removeClass('hidden');
      dragDiv.bind('mousemove', movefunc);
      dragDiv.bind('mouseup', upfunc);
    });
  };
});
*/
