'use strict';

angular.module('playgroundApp', ['playgroundApp.filters',
                                 'playgroundApp.services',
                                 'playgroundApp.directives'])

.config(function($locationProvider, $routeProvider) {

  $locationProvider.html5Mode(true);

  $routeProvider
  .otherwise({redirectTo: '/playground/'});

})

// *** TODO: TEST EVERYTHING BELOW THIS LINE *****

.config(function($httpProvider, $locationProvider, $routeProvider) {
  $httpProvider.responseInterceptors.push('playgroundHttpInterceptor');

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

})
