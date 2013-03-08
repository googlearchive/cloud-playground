'use strict';

angular.module('playgroundApp', [
    'playgroundApp.filters',
    'playgroundApp.services',
    'playgroundApp.directives',
    'ui.bootstrap',
    'ui',
])

.config(function($locationProvider, $routeProvider, $httpProvider,
                 $dialogProvider) {

  $locationProvider.html5Mode(true);

  // TODO: add list of promises to be resolved for injection
  // TODO: resolved promises are injected into controller
  // TODO: see http://www.youtube.com/watch?v=P6KITGRQujQ
  $routeProvider
  .when('/playground/', {
     templateUrl: '/playground/main.html',
     controller: MainController,
  })
  .when('/playground/p/:project_id/', {
     templateUrl: '/playground/project.html',
     controller: ProjectController,
  });

  $httpProvider.responseInterceptors.push('playgroundHttpInterceptor');

  // TODO: test these defaults?
  $dialogProvider.options({
      backdropFade: true,
      modalFade: true,
  });

})

.value('ui.config', {
  codemirror: {
    lineNumbers: true,
    matchBrackets: true,
    autofocus: true,
    undoDepth: 440, // default = 40
  }
})

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

});
