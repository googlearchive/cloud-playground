'use strict';

/* jasmine specs for controllers */

/* http://docs.angularjs.org/api/angular.mock.inject */

function make_project(key, subsecond) {
  return {
      'description': 'The project description',
      'key': key,
      'name': 'New project name',
      'orderby': 'test@example.com-2013-01-03T01:05:32.' + subsecond,
      'run_url': 'http://localhost:9200/?_mimic_project=' + key,
  }
};

describe('HeaderController', function() {
  var scope, location;

  beforeEach(inject(function($rootScope, $controller, $location) {
    scope = $rootScope.$new();
    $controller(HeaderController, {$scope: scope});
    location = $location
  }));


  it('alreadyhome function should only return true for /playground/', function() {
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



describe('ProjectController', function() {

  var scope, $httpBackend;

  function make_files_response() {
    return [
        { 'mime_type': 'text/x-yaml',
          'name': 'app.yaml', },
        { 'mime_type': 'image/x-icon',
          'name': 'favicon.ico', },
        { 'mime_type': 'text/x-python',
          'name': 'main.py', }
    ];
  }

  function make_files_data() {
    return {
        'app.yaml': { 'mime_type': 'text/x-yaml',
                      'name': 'app.yaml', },
        'favicon.ico': { 'mime_type': 'image/x-icon',
                         'name': 'favicon.ico', },
        'main.py': { 'mime_type': 'text/x-python',
                     'name': 'main.py', }
    };
  }

  beforeEach(module(function($provide) {
    $provide.factory('$window', function() {
      return {
        location: { replace: jasmine.createSpy() },
        navigator: {},
      };
    });
  }));

  beforeEach(module('playgroundApp.services'));

  beforeEach(inject(function($rootScope, $injector) {
    scope = $rootScope.$new();
    $httpBackend = $injector.get('$httpBackend');

    $httpBackend
    .when('GET', '/playground/p/20/listfiles')
    .respond(make_files_response())
  }));


  afterEach(function() {
    $httpBackend.verifyNoOutstandingExpectation();
    $httpBackend.verifyNoOutstandingRequest();
  });


  describe('initialization', function() {

    it('should set $scope.project to the project identified by $routeParams.project_id', inject(function($routeParams, $controller) {
      $routeParams.project_id = 42;
      var project = make_project(42);
      scope.projects = [make_project(17), project, make_project(13)];
      expect(scope.projects[1]).toBe(project);
      expect(scope.project).toBeUndefined();
      $httpBackend.expectGET('http://server/listfiles').respond('');
      $controller(ProjectController, {$scope: scope});
      flushDoSerial();
      $httpBackend.flush();
      expect(scope.project).toBe(project);
    }));

    it('should call /playground/p/:project_id/listfiles', inject(function($controller, $browser) {
      $browser.url('/playground/p/20/');
      $httpBackend.expectGET('/playground/p/20/listfiles');
      $controller(ProjectController, {$scope: scope});
      flushDoSerial();
      $httpBackend.flush();
    }));

  });


  describe('is_image_mime_type function', function() {

    it('should return true for image/* MIME Types', inject(function($controller) {
      $controller(ProjectController, {$scope: scope});
      expect(scope.is_image_mime_type('image/png')).toBe(true);
      expect(scope.is_image_mime_type('image/gif')).toBe(true);
      expect(scope.is_image_mime_type('image')).toBe(false);
      expect(scope.is_image_mime_type('text/plain')).toBe(false);
      expect(scope.is_image_mime_type('text/png')).toBe(false);
      expect(scope.is_image_mime_type('application/octet-stream')).toBe(false);
    }));

  });


  describe('_list_files function', function() {

    it('should call /playground/p/:project_id/listfiles', inject(function($controller, $browser, $http) {
      $browser.url('/playground/p/20/');
      expect(scope.files).toBeUndefined();
      $httpBackend.expectGET('/playground/p/20/listfiles');
      $controller(ProjectController, {$scope: scope});
      scope._list_files();
      $httpBackend.flush();
      expect(scope.files).toEqual(make_files_data());
    }));

  });


  describe('_select_first_file function', function() {

    it('should call $scope.select(:first_file)', inject(function($controller) {
      $controller(ProjectController, {$scope: scope});
      scope.select = jasmine.createSpy();
      scope.files = make_files_data();
      expect(scope.select).not.toHaveBeenCalled();
      scope._select_first_file();
      expect(scope.select).toHaveBeenCalledWith({mime_type: 'text/x-yaml',
                                                 name: 'app.yaml'});
    }));

  });

});

describe('PageController', function() {

  describe('initialization', function() {

    var scope, $httpBackend;

    beforeEach(module('playgroundApp.services'));

    beforeEach(inject(function($rootScope, $injector) {
      scope = $rootScope.$new();
      $httpBackend = $injector.get('$httpBackend');

      $httpBackend
      .when('GET', '/playground/getconfig')
      .respond({
          'PLAYGROUND_USER_CONTENT_HOST': 'localhost:9100',
          'email': 'user_q0inuf3vs5',
          'git_playground_url': 'http://code.google.com/p/cloud-playground/',
          'is_admin': false,
          'is_logged_in': false,
          'playground_namespace': '_playground',
      });

      $httpBackend
      .when('GET', '/playground/getprojects')
      .respond([]);
    }));


    afterEach(function() {
      $httpBackend.verifyNoOutstandingExpectation();
      $httpBackend.verifyNoOutstandingRequest();
    });


    it('should, when instantiated, get configuration, then project data', inject(function($controller) {
      expect(scope.config).toBeUndefined();
      expect(scope.projects).toBeUndefined();
      $httpBackend.expectGET('/playground/getconfig');
      $httpBackend.expectGET('/playground/getprojects');
      $controller(PageController, {$scope: scope});
      flushDoSerial();
      $httpBackend.flush();
      expect(scope.config).toBeDefined();
      expect(scope.config.email).toBeDefined();
      expect(scope.config.playground_namespace).toBe('_playground');
      expect(scope.projects).toBeDefined();
      expect(scope.projects.length).toBe(0);
    }));

  });


  describe('namespace function', function() {

    var scope, routeParams;

    beforeEach(module('playgroundApp.services'));

    beforeEach(inject(function($rootScope, $controller, $routeParams) {
      scope = $rootScope.$new();
      scope.config = {};
      routeParams = $routeParams;
      routeParams.project_id = undefined;
      $controller(PageController, {$scope: scope});
    }));


    it('should have no default', function() {
      expect(scope.namespace()).toBeUndefined();
    });


    it('should use $routeParams project_id', function() {
      expect(scope.namespace()).toBeUndefined();
      routeParams.project_id = 'route_param';
      expect(scope.namespace()).toBe('route_param');
    });


    it('should use $scope.config.playground_namespace', function() {
      expect(scope.namespace()).toBeUndefined();
      scope.config.playground_namespace = 'pg_namepsace';
      expect(scope.namespace()).toBe('pg_namepsace');
    });


    it('should prefer $routeParams to $scope.config', function() {
      expect(scope.namespace()).toBeUndefined();
      routeParams.project_id = 'route_param';
      scope.config.playground_namespace = 'pg_namepsace';
      expect(scope.namespace()).toBe('route_param');
    });

  });


  describe('datastore_admin function', function() {

    var scope;

    beforeEach(module('playgroundApp.services'));

    beforeEach(inject(function($rootScope, $controller, $routeParams, $window) {
      scope = $rootScope.$new();
      $routeParams.project_id = 'some_namespace';
      $window.open = jasmine.createSpy();
      $controller(PageController, {$scope: scope});
    }));


    it('should open new window to /playground/datastore/some_namespace', inject(function($window) {
      expect($window.open).not.toHaveBeenCalled();
      scope.datastore_admin();
      expect($window.open).toHaveBeenCalledWith('/playground/datastore/some_namespace', '_blank');
    }));

  });


  describe('memcache_admin function', function() {

    var scope;

    beforeEach(module('playgroundApp.services'));

    beforeEach(inject(function($rootScope, $controller, $routeParams, $window) {
      scope = $rootScope.$new();
      $routeParams.project_id = 'some_namespace';
      $window.open = jasmine.createSpy();
      $controller(PageController, {$scope: scope});
    }));


    it('should open new window to /playground/memcache/some_namespace', inject(function($window) {
      expect($window.open).not.toHaveBeenCalled();
      scope.memcache_admin();
      expect($window.open).toHaveBeenCalledWith('/playground/memcache/some_namespace', '_blank');
    }));

  });

});


describe('MainController', function() {

  var scope, $httpBackend;

  beforeEach(module('playgroundApp.services'));

  beforeEach(module(function($provide) {
    $provide.factory('$window', function() {
      return {
        location: { replace: jasmine.createSpy() },
        navigator: {},
      };
    });
  }));

  beforeEach(inject(function($rootScope, $injector) {
    scope = $rootScope.$new();
    scope.projects = [];
    $httpBackend = $injector.get('$httpBackend');

    $httpBackend
    .when('GET', '/playground/gettemplates')
    .respond({
        'template_sources': [
          { 'key': 'foo_key', 'description': 'foo_description' },
          { 'key': 'bar_key', 'description': 'bar_description' },
        ],
        'templates': [
          { 'key': 'boo_key', 'description': 'boo_description',
            'name': 'boo_name', 'source_key': 'boo_source_key' },
        ]
    });

    $httpBackend
    .when('GET', '/playground/getprojects')
    .respond([]);
  }));

  afterEach(function() {
    $httpBackend.verifyNoOutstandingExpectation();
    $httpBackend.verifyNoOutstandingRequest();
  });

  function doInit() {
    inject(function($controller) {
      $controller(MainController, {$scope: scope});
      flushDoSerial();
      $httpBackend.flush();
    });
  }


  describe('initialization', function() {

    it('should transition $scope.loaded state to true', inject(function($controller) {
      expect(scope.loaded).toBeUndefined();
      doInit();
      expect(scope.loaded).toBe(true);
    }));

    it('should get templates', inject(function($controller) {
      expect(scope.templates).toBeUndefined();
      $httpBackend.expectGET('/playground/gettemplates');
      doInit();
      expect(scope.templates).toBeDefined();
      expect(scope.templates.template_sources.length).toBe(2);
      expect(scope.templates.template_sources[0].key).toBe('foo_key');
      expect(scope.templates.template_sources[0].description).toBe('foo_description');
      expect(scope.templates.template_sources[1].key).toBe('bar_key');
      expect(scope.templates.template_sources[1].description).toBe('bar_description');
      expect(scope.templates.templates).toBeDefined();
      expect(scope.templates.templates.length).toBe(1);
      expect(scope.templates.templates[0].key).toBe('boo_key');
      expect(scope.templates.templates[0].description).toBe('boo_description');
      expect(scope.templates.templates[0].name).toBe('boo_name');
      expect(scope.templates.templates[0].source_key).toBe('boo_source_key');
    }));

  });


  describe('runtime behavior', function() {

    var location;

    beforeEach(inject(function($controller, $location) {
      $controller(MainController, {$scope: scope});
      flushDoSerial();
      $httpBackend.flush();
      location = $location;
    }));


    describe('login function', function() {

      it('should navigate to /playground/login', inject(function($window) {
        expect($window.location.replace).not.toHaveBeenCalled();
        scope.login();
        expect($window.location.replace).toHaveBeenCalledWith('/playground/login');
      }));

    });


    describe('new_project function', function() {

      beforeEach(function() {
        $httpBackend
        .when('POST', '/playground/createproject')
        .respond(make_project(42, 1));
      });

      it('should call /playground/createproject', inject(function() {
        expect(scope.projects).toBeDefined();
        expect(scope.templates.templates).toBeDefined();
        expect(scope.templates.templates.length).toBeGreaterThan(0);
        $httpBackend.expectPOST('/playground/createproject');
        scope.new_project(scope.templates.templates[0]);
        flushDoSerial();
        $httpBackend.flush();
        expect(scope.projects.length).toBe(1);
        expect(scope.projects[0].key).toBe(42);
        expect(scope.projects[0].name).toBe('New project name');
      }));

    });


    describe('select_project function', function() {

      beforeEach(function() {
        $httpBackend
        .when('POST', '/playground/p/15/touch')
        .respond(make_project(15, 2));
      });


      it('should call /playground/p/:project_id/touch', function() {
        var project = make_project(15, 1);
        scope.projects = [make_project(14, 1), project, make_project(16, 1),
                          make_project(17, 1)];
        expect(scope.projects[1]).toEqual(make_project(15, 1));
        expect(location.path()).toEqual('');
        scope.select_project(project);
        flushDoSerial();
        $httpBackend.flush();
        expect(scope.projects[1]).not.toEqual(make_project(15, 1));
        expect(scope.projects[1]).toEqual(make_project(15, 2));
        expect(location.path()).toEqual('/playground/p/15');
      });

    });

  });

});
