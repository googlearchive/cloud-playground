'use strict';

angular.module('playgroundApp', [
    'playgroundApp.filters',
    'playgroundApp.services',
    'playgroundApp.directives',
    'ngRoute',
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
     reloadOnSearch: false,
  });

  $httpProvider.interceptors.push('pgHttpInterceptor');

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
});
