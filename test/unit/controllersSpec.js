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


xdescribe('MyCtrl2', function() {
  var myCtrl2;

  beforeEach(function(){
    myCtrl2 = new MyCtrl2();
  });

  xit('should ....', function() {
    //spec body
  });
});
