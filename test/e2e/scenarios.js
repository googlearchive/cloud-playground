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


  it('should have HTML5 mode enabled', function() {
    expect(browser().window().path()).toBe("/playground/");
  })


  it('should automatically redirect to /playground/', function() {
    expect(browser().location().url()).toBe("/playground/");
  });


  describe('main page', function() {

    beforeEach(function() {
      browser().navigateTo('/playground/');
    });


    it('should render main view', function() {
      //expect(element('[ng-view]').text()).toMatch(/My Projects/);
    });

    it('should show warning', function() {
      expect(element('body').text()).toMatch(/Anyone can read, modify or delete your projects/);
    });

    it('should have login/logout buttons', function() {
      expect(element('body').text()).toMatch(/login/);
      expect(element('body').text()).toMatch(/logout/);
    });

  });


  describe('project', function() {

    beforeEach(function() {
      browser().navigateTo('/playground/p/42/');
    });


    it('should render project view', function() {
      //expect(element('[ng-view]').text()).toMatch(/\+ new file/);
    });

  });
});
