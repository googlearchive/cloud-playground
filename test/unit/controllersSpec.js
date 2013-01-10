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

  var scope, $httpBackend, location;

  beforeEach(inject(function($rootScope, $injector) {
    scope = $rootScope.$new();
    //$httpBackend = $injector.get('$httpBackend');
  }));

  beforeEach(inject(function($location) {
    doInit();
    location = $location
  }));

  function doInit() {
    inject(function($controller) {
      $controller(HeaderController, {$scope: scope});
      flushDoSerial();
      //$httpBackend.flush();
    });
  }


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

  function make_file(filename, mime_type, contents) {
    var file = {
        'name': filename,
        'mime_type': mime_type,
    };
    if (contents) {
      file.contents = contents;
    }
    return file;
  }

  function make_files_response() {
    return [
        make_file('app.yaml',    'text/x-yaml'),
        make_file('favicon.ico', 'image/x-icon'),
        make_file('main.py',     'text/x-python'),
    ];
  }

  function make_files_data() {
    return {
        'app.yaml':    make_file('app.yaml',    'text/x-yaml'),
        'favicon.ico': make_file('favicon.ico', 'image/x-icon'),
        'main.py':     make_file('main.py',     'text/x-python'),
    };
  }

  beforeEach(module(function($provide) {
    $provide.factory('$window', function() {
      return {
        location: { replace: jasmine.createSpy(),
                    pathname: '/playground/p/76/' },
        navigator: {},
      };
    });
  }));

  beforeEach(module('playgroundApp.services'));

  beforeEach(inject(function($rootScope, $injector) {
    scope = $rootScope.$new();
    // TODO: remove if we instead instantiate a PageController
    scope.config = {
        'PLAYGROUND_USER_CONTENT_HOST': 'localhost:9100',
    };
    $httpBackend = $injector.get('$httpBackend');

    $httpBackend
    .whenGET('/playground/p/20/listfiles')
    .respond(make_files_response())
  }));

  beforeEach(inject(function($browser) {
    $browser.url('/playground/p/20/');
  }));


  afterEach(function() {
    flushDoSerial();
    $httpBackend.verifyNoOutstandingExpectation();
    $httpBackend.verifyNoOutstandingRequest();
  });


  function doInit() {
    inject(function($controller) {
      $controller(ProjectController, {$scope: scope});
      flushDoSerial();
      $httpBackend.flush();
    });
  }


  describe('initialization', function() {

    it('should set $scope.project to the project identified by $routeParams.project_id', inject(function($routeParams) {
      $routeParams.project_id = 42;
      var project = make_project(42);
      scope.projects = [make_project(17), project, make_project(13)];
      expect(scope.projects[1]).toBe(project);
      expect(scope.project).toBeUndefined();
      doInit();
      expect(scope.project).toBe(project);
    }));

    it('should call /playground/p/:project_id/listfiles', function() {
      $httpBackend.expectGET('/playground/p/20/listfiles');
      doInit();
    });

  });


  describe('runtime behavior', function() {

    beforeEach(function() {
      doInit();
    });

    describe('no_json_transform function', function() {

      it('should provide the identity transform', function() {
        var data = 'foo';
        expect(scope.no_json_transform(data)).toBe(data);
        expect(scope.no_json_transform(data)).toEqual('foo');
        data = '[1,2,3]';
        expect(scope.no_json_transform(data)).toBe(data);
        expect(scope.no_json_transform(data)).toEqual('[1,2,3]');
        data = undefined;
        expect(scope.no_json_transform(data)).toBe(undefined);
        data = null;
        expect(scope.no_json_transform(data)).toBe(null);
        data = Error('x');
        expect(scope.no_json_transform(data)).toEqual(Error('x'));
        expect(scope.no_json_transform(data)).toBe(data);
      });

    });


    describe('is_image_mime_type function', function() {

      it('should return true for "image/*" MIME types', function() {
        expect(scope.is_image_mime_type('image/png')).toBe(true);
        expect(scope.is_image_mime_type('image/gif')).toBe(true);
        expect(scope.is_image_mime_type('image')).toBe(false);
        expect(scope.is_image_mime_type('text/plain')).toBe(false);
        expect(scope.is_image_mime_type('text/png')).toBe(false);
        expect(scope.is_image_mime_type('application/octet-stream')).toBe(false);
      });

    });


    describe('url_of function', function() {

      it('should return //localhost:9100/p/:project_id/getfile/:filename', inject(function($window) {
        $window.location.pathname = '/playground/p/42/';
        var png = make_file('logo.png', 'image/png');
        expect(scope.url_of(png)).toEqual('//localhost:9100/playground/p/42/getfile/logo.png');
      }));

    });


    describe('image_url_of function', function() {

      it('should return emtpty string when no file is given', function() {
        expect(scope.image_url_of()).toEqual('');
        expect(scope.image_url_of(null)).toEqual('');
      });

      it('should return empty string for none "image/*" MIME types ', function() {
        expect(scope.image_url_of(make_file('filename', 'text/html'))).toEqual('');
      });

      it('should pass through to url_of() for "image/*" MIME types ', function() {
        var png = make_file('filename', 'image/png');
        var file_url = scope.url_of(png);
        expect(scope.image_url_of(png)).toBe(file_url);
      });

    });


    describe('_get function', function() {

      it('should call success_cb when file has contents', function() {
        var success_cb = jasmine.createSpy();
        var file = make_file('app.yaml', 'text/x-yaml', 'version: 1');
        scope._get(file, success_cb);
        expect(success_cb).toHaveBeenCalledWith();
      });

      it('should call success_cb when file has no contents', function() {
        var success_cb = jasmine.createSpy();
        var file = make_file('app.yaml', 'text/x-yaml');
        expect(file.contents).toBeUndefined();
        expect(file.hasOwnProperty('contents')).toBe(false);
        $httpBackend.expectGET(scope.url_of(file)).respond('foo: bar');
        scope._get(file, success_cb);
        $httpBackend.flush();
        expect(file.contents).toEqual('foo: bar');
        expect(success_cb).toHaveBeenCalledWith();
      });

      it('should not overwrite file contents regardless of dirty flag', function() {
        var noop = function() {};
        var file = make_file('app.yaml', 'text/x-yaml', 'version: 1');
        scope._get(file, noop);
        expect(file.dirty).not.toBeDefined();
        expect(file.hasOwnProperty('dirty')).toBe(false);
        expect(file.contents).toEqual('version: 1');
        file.dirty = true;
        scope._get(file, noop);
        expect(file.contents).toEqual('version: 1');
        file.dirty = false;
        scope._get(file, noop);
        expect(file.contents).toEqual('version: 1');
      });

      it('should set file.dirty=false after fetching contents', function() {
        var success_cb = jasmine.createSpy();
        var file = make_file('app.yaml', 'text/x-yaml');
        expect(file.contents).toBeUndefined();
        expect(file.hasOwnProperty('contents')).toBe(false);
        expect(file.dirty).toBe(undefined);
        $httpBackend.expectGET(scope.url_of(file)).respond('version: bar');
        scope._get(file, success_cb);
        $httpBackend.flush();
        expect(file.contents).toEqual('version: bar');
        expect(file.dirty).toBe(false);
      });

      it('should HTTP GET missing file contents', function() {
        var success_cb = jasmine.createSpy();
        var file = make_file('app.yaml', 'text/x-yaml');
        $httpBackend.expectGET(scope.url_of(file)).respond('x: y');
        expect(file.contents).toBeUndefined();
        scope._get(file, success_cb);
        $httpBackend.flush();
        expect(file.contents).toEqual('x: y');
      });

    });


    describe('_list_files function', function() {

      function make_plain_file() {
        return make_file('foo.txt', 'text/plain');
      }

      it('should call /playground/p/:project_id/listfiles', function() {
        $httpBackend.verifyNoOutstandingRequest();
        $httpBackend.verifyNoOutstandingExpectation();
        expect(scope.files).toEqual(make_files_data());
        $httpBackend
        .expectGET('/playground/p/20/listfiles')
        .respond([make_plain_file()]);
        scope.files = null;
        scope._list_files();
        $httpBackend.flush();
        expect(scope.files).toEqual({'foo.txt': make_plain_file()});
      });

    });


    describe('select_file function', function() {

      describe('with "image/*" MIME types', function() {

        function make_image_file() {
          return make_file('foo.png', 'image/png');
        }

        it('should set $scope.current_file', function() {
          expect(scope.current_file).toBeUndefined();
          scope.select_file(make_image_file());
          expect(scope.current_file).toEqual(make_image_file());
        });

        it('should return undefined', function() {
          var result = scope.select_file(make_image_file());
          expect(result).toBeUndefined();
        });

      });

      describe('with MIME types other than "image/*"', function() {

        function make_text_file() {
          return make_file('app.yaml', 'text/x-yaml', 'version: 1');
        }

        beforeEach(function() {
          scope.create_editor = jasmine.createSpy();
        });

        it('should set $scope.current_file', function() {
          expect(scope.current_file).toBeUndefined();
          scope.select_file(make_text_file());
          flushDoSerial();
          expect(scope.current_file).toEqual(make_text_file());
        });

        it('should call DoSerial.then() and DoSerial.tick()', inject(function(DoSerial) {
          spyOn(DoSerial, 'then').andCallThrough();
          spyOn(DoSerial, 'tick').andCallThrough();
          scope.select_file(make_text_file());
          expect(DoSerial.then).toHaveBeenCalled();
          expect(DoSerial.tick).toHaveBeenCalled();
        }));

        it('should call $scope.create_editor(:mime_type)', function() {
          scope.select_file(make_text_file());
          flushDoSerial();
          expect(scope.create_editor).toHaveBeenCalledWith('text/x-yaml');
        });

      });

    });

    describe('_select_first_file function', function() {

      it('should call $scope.select_file(:first_file)', function() {
        scope.select_file = jasmine.createSpy();
        scope.files = make_files_data();
        expect(scope.select_file).not.toHaveBeenCalled();
        scope._select_first_file();
        var expected_file = make_file('app.yaml', 'text/x-yaml');
        expect(scope.select_file).toHaveBeenCalledWith(expected_file);
      });

    });

  });

});

describe('PageController', function() {

  var scope, $httpBackend;

  function doInit() {
    inject(function($controller) {
      $controller(PageController, {$scope: scope});
      flushDoSerial();
      $httpBackend.flush();
    });
  }

    beforeEach(module('playgroundApp.services'));

    beforeEach(inject(function($rootScope, $injector) {
      scope = $rootScope.$new();
      $httpBackend = $injector.get('$httpBackend');

      $httpBackend
      .whenGET('/playground/getconfig')
      .respond({
          'PLAYGROUND_USER_CONTENT_HOST': 'localhost:9100',
          'email': 'user_q0inuf3vs5',
          'git_playground_url': 'http://code.google.com/p/cloud-playground/',
          'is_admin': false,
          'is_logged_in': false,
          'playground_namespace': '_playground',
      });

      $httpBackend
      .whenGET('/playground/getprojects')
      .respond([]);
    }));


  describe('initialization', function() {

    afterEach(function() {
      flushDoSerial();
      $httpBackend.verifyNoOutstandingExpectation();
      $httpBackend.verifyNoOutstandingRequest();
    });


    it('should, when instantiated, get configuration, then project data', function() {
      expect(scope.config).toBeUndefined();
      expect(scope.projects).toBeUndefined();
      $httpBackend.expectGET('/playground/getconfig');
      $httpBackend.expectGET('/playground/getprojects');
      doInit();
      expect(scope.config).toBeDefined();
      expect(scope.config.email).toBeDefined();
      expect(scope.config.playground_namespace).toBe('_playground');
      expect(scope.projects).toBeDefined();
      expect(scope.projects.length).toBe(0);
    });

  });


  describe('runtion behavior', function() {

    beforeEach(function() {
      doInit();
    });

    describe('namespace function', function() {

      var routeParams;

      beforeEach(inject(function($routeParams) {
        scope.config = {};
        routeParams = $routeParams;
        routeParams.project_id = undefined;
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


    describe('link functions', function() {

      beforeEach(inject(function($routeParams, $window) {
        $routeParams.project_id = 'some_namespace';
        $window.open = jasmine.createSpy();
      }));


      describe('datastore_admin function', function() {

        it('should open new window to /playground/datastore/some_namespace', inject(function($window) {
          expect($window.open).not.toHaveBeenCalled();
          scope.datastore_admin();
          expect($window.open).toHaveBeenCalledWith('/playground/datastore/some_namespace', '_blank');
        }));

      });


      describe('memcache_admin function', function() {

        it('should open new window to /playground/memcache/some_namespace', inject(function($window) {
          expect($window.open).not.toHaveBeenCalled();
          scope.memcache_admin();
          expect($window.open).toHaveBeenCalledWith('/playground/memcache/some_namespace', '_blank');
        }));

      });

    });

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
    .whenGET('/playground/gettemplates')
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
    .whenGET('/playground/getprojects')
    .respond([]);
  }));

  afterEach(function() {
    flushDoSerial();
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

    it('should transition $scope.loaded state to true', function() {
      expect(scope.loaded).toBeUndefined();
      doInit();
      expect(scope.loaded).toBe(true);
    });

    it('should get templates', function() {
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
    });

  });


  describe('runtime behavior', function() {

    var location;

    beforeEach(inject(function( $location) {
      doInit();
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
