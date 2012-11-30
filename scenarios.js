'use strict';

/* http://docs.angularjs.org/guide/dev_guide.e2e-testing */

describe('cloud playground app', function() {

  beforeEach(function() {
    browser().navigateTo('/');
  });

  afterEach(function() {
    //sleep(1.5);
    //pause();
  });

  it('should automatically redirect to /playground/', function() {
    expect(browser().location().url()).toBe("/playground/");
    //expect(browser()).toBe(true);
    //console.log(browser().location().url());
    //expect(browser().location()).toBe(true);
  });


  describe('home', function() {

    beforeEach(function() {
      //browser().navigateTo('/playground/');
    });


    it('should render main view', function() {
      //expect(element('[ng-view]').text()).toMatch(/My Projects/);
    });

  });


  describe('project', function() {

    beforeEach(function() {
      //browser().navigateTo('/playground/p/42/');
    });


    it('should render project view', function() {
      //expect(element('[ng-view]').text()).toMatch(/\+ new file/);
    });

  });
});
