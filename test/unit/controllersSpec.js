'use strict';

/* jasmine specs for controllers */

describe('HeaderController', function() {
  var scope, ctrl, location;

  beforeEach(inject(function($rootScope, $controller, $location) {
    scope = $rootScope.$new();
    ctrl = $controller(HeaderController, {$scope: scope});
    location = $location
  }));


  it('should provide "alreadyhome" function', function() {
    expect(typeof scope.alreadyhome).toEqual('function');

    location.path('/');
    expect(scope.alreadyhome()).toBe(false);
    location.path('/playground');
    expect(scope.alreadyhome()).toBe(false);
    location.path('/playground/');
    expect(scope.alreadyhome()).toBe(true);
    location.path('/playground/p/42/');
    expect(scope.alreadyhome()).toBe(false);
  });

});


describe('PageController', function() {

  var scope, controller, $httpBackend;

  describe('initialization', function () {

    beforeEach(module('playgroundApp.services'));

    beforeEach(inject(function($rootScope, $controller, $injector) {
      scope = $rootScope.$new();
      controller = $controller;
      $httpBackend = $injector.get('$httpBackend');

      $httpBackend
      .when('GET', '/playground/getconfig')
      .respond({
          "PLAYGROUND_USER_CONTENT_HOST": "localhost:9100",
          "email": "user_q0inuf3vs5",
          "git_playground_url": "http://code.google.com/p/cloud-playground/",
          "is_admin": false,
          "is_logged_in": false,
          "playground_namespace": "_playground",
      });

      $httpBackend
      .when('GET', '/playground/getprojects')
      .respond([]);
    }));


    afterEach(function() {
      $httpBackend.verifyNoOutstandingExpectation();
      $httpBackend.verifyNoOutstandingRequest();
    });


    it('should, when instantiated, get configuration, then project data', inject(function($timeout) {
      expect(scope.config).toBeUndefined();
      expect(scope.projects).toBeUndefined();
      $httpBackend.expectGET('/playground/getconfig');
      $httpBackend.expectGET('/playground/getprojects');
      var ctrl = controller(PageController, {$scope: scope});
      flushDoSerial($timeout);
      $httpBackend.flush();
      expect(scope.config).toBeDefined();
      expect(scope.config.email).toBeDefined();
      expect(scope.config.playground_namespace).toBe('_playground');
      expect(scope.projects).toBeDefined();
      expect(scope.projects.length).toBe(0);
    }));

  });


  describe('namespace function', function() {

    var scope, ctrl;

    beforeEach(module('playgroundApp.services'));

    beforeEach(inject(function($rootScope, $controller, $injector, $routeParams) {
      scope = $rootScope.$new();
      scope.config = {};
      $routeParams.project_id = undefined;
      ctrl = $controller(PageController, {$scope: scope});
    }));


    it('should have no default', inject(function($routeParams) {
      expect(scope.namespace()).toBeUndefined();
    }));


    it('should use $routeParams project_id', inject(function($routeParams) {
      expect(scope.namespace()).toBeUndefined();
      $routeParams.project_id = 'route_param';
      expect(scope.namespace()).toBe('route_param');
    }));


    it('should use $scope.config.playground_namespace', inject(function($routeParams) {
      expect(scope.namespace()).toBeUndefined();
      scope.config.playground_namespace = 'pg_namepsace';
      expect(scope.namespace()).toBe('pg_namepsace');
    }));


    it('should prefer $routeParams to $scope.config', inject(function($routeParams) {
      expect(scope.namespace()).toBeUndefined();
      $routeParams.project_id = 'route_param';
      scope.config.playground_namespace = 'pg_namepsace';
      expect(scope.namespace()).toBe('route_param');
    }));

  });



  describe('datastore_admin function', function() {

    var scope, ctrl;

    beforeEach(module('playgroundApp.services'));

    beforeEach(inject(function($rootScope, $controller, $injector, $routeParams, $window) {
      scope = $rootScope.$new();
      $routeParams.project_id = 'some_namespace';
      $window.open = jasmine.createSpy();
      ctrl = $controller(PageController, {$scope: scope});
    }));


    it('should open new window to /playground/datastore/some_namespace', inject(function($window) {
      expect($window.open).not.toHaveBeenCalled();
      scope.datastore_admin();
      expect($window.open).toHaveBeenCalledWith('/playground/datastore/some_namespace', '_blank');
    }));

  });

});
