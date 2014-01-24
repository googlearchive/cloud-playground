'use strict';

window.track = function(action, label, label_detail) {
  var category = 'cloud-playground';
  if (label_detail !== undefined) {
    label = label + ':' + label_detail;
  }
  // console.log(action, label);
  ga(function() {
    var trackers = ga.getAll();
    for (var index = 0; index < trackers.length; index++) {
      trackers[index].send('event', category, action, label);
    }
  });
};

window.iframed = window.top != window.self;

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
    resolve: {
      'CookieFinder': 'CookieFinder',
      'NeededByPageControllerConfigService': 'ConfigService',
      'NeededByPageControllerProjectsFactory': 'ProjectsFactory',
      'Projects': 'ProjectsFactory',
    },
  })
  .when('/playground/p/:project_id/', {
    templateUrl: '/playground/project.html',
    controller: ProjectController,
    reloadOnSearch: false,
    resolve: {
      'CookieFinder': 'CookieFinder',
      'NeededByPageControllerConfigService': 'ConfigService',
      'NeededByPageControllerProjectsFactory': 'ProjectsFactory',
      'Projects': 'ProjectsFactory',
    },
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
