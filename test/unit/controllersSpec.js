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
    .respond();

    $httpBackend
    .when('GET', '/playground/getprojects')
    .respond();
  }));


  afterEach(function() {
    $httpBackend.verifyNoOutstandingExpectation();
    $httpBackend.verifyNoOutstandingRequest();
  });


  it('should, when instantiated, get configuration, then project data', function() {
    $httpBackend.expectGET('/playground/getconfig');
    $httpBackend.expectGET('/playground/getprojects');
    var ctrl = controller(PageController, {$scope: scope});
    $httpBackend.flush();
  });
});
