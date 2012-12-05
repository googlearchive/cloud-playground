'use strict';

/* jasmine specs for services */

describe('app config', function() {

  beforeEach(module('playgroundApp'));


  it('should install playgroundHttpInterceptor', function() {

    var httpProvider;

    module(function($httpProvider) {
      httpProvider = $httpProvider;
    });

    inject(function() {
      expect(httpProvider.responseInterceptors).toEqual(['playgroundHttpInterceptor']);
    });

  });

});
