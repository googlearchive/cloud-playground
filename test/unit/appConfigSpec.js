'use strict';

/* jasmine specs for app config */

describe('app config', function() {

  beforeEach(module('playgroundApp'));


  it('should install pgHttpInterceptor', function() {

    var httpProvider;

    module(function($httpProvider) {
      httpProvider = $httpProvider;
    });

    inject(function() {
      expect(httpProvider.responseInterceptors)
      .toEqual(['pgHttpInterceptor']);
    });

  });


  it('should enable html5Mode', function() {

    var locationProvider;

    module(function($locationProvider) {
      locationProvider = $locationProvider;
    });

    inject(function() {
      expect(locationProvider.html5Mode()).toEqual(true);
    });

  });

});
