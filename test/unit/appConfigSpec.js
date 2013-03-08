'use strict';

/* jasmine specs for app config */

describe('app config', function() {

  beforeEach(module('playgroundApp'));


  it('should install playgroundHttpInterceptor', function() {

    var httpProvider;

    module(function($httpProvider) {
      httpProvider = $httpProvider;
    });

    inject(function() {
      expect(httpProvider.responseInterceptors)
        .toEqual(['playgroundHttpInterceptor']);
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
