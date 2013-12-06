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


  it('should perform html5Mode redirect with trailing slash', function() {
    expect(browser().window().path()).toBe('/playground/');
  });


  it('should automatically redirect to /playground/', function() {
    expect(browser().location().url()).toBe('/playground/');
  });


  describe('login behavior', function() {

    var current_url = 'http://localhost:7070/playground/';

    function logout() {
      expect(browser().window().href()).toBe(current_url);
      browser().navigateTo('/_ah/login?action=Logout&continue=' + current_url);
      expect(browser().window().href()).toBe(current_url);
    }

    function login(admin) {
      expect(browser().window().href()).toBe(current_url);
      browser().navigateTo('/_ah/login?email=test@example.com&admin=' +
                           (admin ? 'True' : 'False') +
                           '&action=Login&continue=' + current_url);
      expect(browser().window().href()).toBe(current_url);
    }


    it('should only provide login button when the user is not logged in',
       function() {
      logout();
      expect(element('button:contains("login")').count()).toEqual(1);
      expect(element('button:contains("login")').css('display'))
        .toEqual('inline-block');
      expect(element('button:contains("login")').height()).toBeGreaterThan(0);
      login(true);
      expect(element('button:contains("login")').count()).toEqual(1);
      expect(element('button:contains("login")').css('display'))
        .toEqual('none');
      // TODO: figure out why this fails:
      //expect(element('button:contains("login")').height()).toEqual(0);
    });


    it('should only provide logout button when the user is logged in',
       function() {
      login(true);
      expect(element('button:contains("logout")').count()).toEqual(1);
      expect(element('button:contains("logout")').css('display'))
        .toEqual('inline-block');
      expect(element('button:contains("logout")').height()).toBeGreaterThan(0);
      logout();
      expect(element('button:contains("logout")').count()).toEqual(1);
      expect(element('button:contains("logout")').css('display'))
        .toEqual('none');
      // TODO: figure out why this fails:
      //expect(element('button:contains("logout")').height()).toEqual(0);
    });


    // commented out since we always show admin links in the dev_appserver
    xit('should only provide admin links when user is logged in as an admin',
        function() {
      login(false);
      expect(element('[ng-click="big_red_button()"]').height()).toEqual(0);
      expect(element('[ng-click="open_datastore_admin()"]').height()).toEqual(0);
      expect(element('[ng-click="open_memcache_admin()"]').height()).toEqual(0);
      login(true);
      expect(element('[ng-click="big_red_button()"]').height())
        .toBeGreaterThan(0);
      expect(element('[ng-click="open_datastore_admin()"]').height())
        .toBeGreaterThan(0);
      expect(element('[ng-click="open_memcache_admin()"]').height())
        .toBeGreaterThan(0);
    });

  });


  describe('main page', function() {

    beforeEach(function() {
      browser().navigateTo('/playground/');
    });


    it('should render main view', function() {
      expect(element('[ng-view]').text()).toMatch(/My Projects/);
    });

    it('should show warning', function() {
      expect(element('body').text())
        .toMatch(/Anyone can read, modify or delete your projects/);
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
      expect(element('[ng-view]').text()).toMatch(/\+ new file/);
    });

  });
});
