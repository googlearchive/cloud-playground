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

  it('should automatically redirect to /playground/', function() {
    //expect(browser().location().url()).toBe("/playground/");
  });

});


describe('PageController', function() {
  var scope, controller, $httpBackend;

  beforeEach(module('playgroundApp'));
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
