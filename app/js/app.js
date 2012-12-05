'use strict';

angular.module('playgroundApp', ['playgroundApp.filters',
                                 'playgroundApp.services',
                                 'playgroundApp.directives'])

.config(function($locationProvider, $routeProvider, $httpProvider) {

  $locationProvider.html5Mode(true);

  $routeProvider
  .when('/playground/', {
     templateUrl: '/playground/main.html',
     controller: MainController,
  })
  .when('/playground/p/:project_id/', {
     templateUrl: '/playground/project.html',
     controller: ProjectController,
  })
  .otherwise({redirectTo: '/playground/'});

  $httpProvider.responseInterceptors.push('playgroundHttpInterceptor');

})
