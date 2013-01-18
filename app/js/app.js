'use strict';

angular.module('playgroundApp', ['playgroundApp.filters',
                                 'playgroundApp.services',
                                 'playgroundApp.directives'])

.config(function($locationProvider, $routeProvider, $httpProvider) {

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
  })

  $httpProvider.responseInterceptors.push('playgroundHttpInterceptor');

})
