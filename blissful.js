angular.module('blissful', ['ngResource'])

.config(function($httpProvider, $locationProvider, $routeProvider) {
  $httpProvider.responseInterceptors.push('blissHttpInterceptor');

  $locationProvider.html5Mode(true);

  $routeProvider
    .when('/bliss/', {
       templateUrl: '/bliss/main.html',
       controller: MainController,
    })
    .when('/bliss/p/:project_id/', {
       templateUrl: '/bliss/project.html',
       controller: ProjectController,
    })
    .otherwise({redirectTo: '/bliss/'});
})

.factory('blissHttpInterceptor', function($q) {
  return function(promise) {
    return promise.then(function(response) {
      return response;
    }, function(err) {
      if (err instanceof Error) {
        alert(err);
      } else if (err.headers('X-Bliss-Error')) {
        alert('Error:\n' + err.data);
      } else {
        // TODO: address problems such as OPTIONS pre-flight request failures
        console.log('err', err);
        alert(err.status + ' <- ' + err.config.method + ' ' + err.config.url +
              '\n' + err.data);
      }
      return $q.reject(err);
    });
  };
})

.factory('Config', function($resource) {
  var Config = $resource('getprojects');
  return Config;
})

.factory('DoSerial', function($timeout, $log) {

  var queue = [];

  var timeout;

  function _success() {
    timeout = null;
    _next();
  }

  function _error() {
    timeout = null;
    if (queue.length > 0) {
      $log.warn('Aborting ' + queue.length + ' queued work item(s)');
      for (item in queue) {
        $log.warn(item, '--', queue[item]);
      }
      queue = [];
    }
  }

  function _next() {
    if (!queue) {
      return;
    }
    if (timeout) {
      return;
    }
    var work = queue.shift()
    if (!work) {
      return;
    }
    timeout = $timeout(work).then(_success, _error);
  }

  return {
    add: function(work) {
      queue.push(work);
      _next();
    }
  }

});

function HeaderController($scope, $location) {

  $scope.alreadyhome = function() {
    return $location.path() == '/bliss/';
  }

}

function AdminController($scope, $http) {

  $scope.big_red_button = function() {
    box = lightbox('Bye, bye, data.', 'Please wait...');
    $http.post('nuke')
    .success(function(data, status, headers, config) {
      box();
      document.body.scrollTop = 0;
      window.location.reload();
    });
  };

}

function MainController($scope, $http, $location, $window, Config) {

  $scope.config = Config.get({}, function(data) { data.loaded=true; });

  $scope.login = function() {
    $window.location = '/bliss/login';
  }

  $scope.select_project = function(project) {
    $location.path('/bliss/p/' + project.key);
  }

  $scope.prompt_for_new_project = function(template) {
    box = lightbox('Creating project', 'Please wait.');
    $http.post('createproject', {
        template_url: template.key,
        project_name: template.name,
        project_description: template.description})
    .success(function(data, status, headers, config) {
      box();
      document.body.scrollTop = 0;
      window.location.reload();
    });
  };

  $scope.prompt_to_delete_project = function(project) {
    var answer = prompt("Are you sure you want to delete project " +
                        project.name + "?\nType 'yes' to confirm.", "no");
    if (!answer || answer.toLowerCase()[0] != 'y') {
      return;
    }
    $http.post('/bliss/p/' + encodeURI(project.key) + '/delete')
    .success(function(data, status, headers, config) {
      document.body.scrollTop = 0;
      window.location.reload();
    });
  };

}

function ProjectController($scope, $http, $resource, $filter, $log, DoSerial) {

  var Files = $resource('listfiles');

  var source_code = document.getElementById('source-code');
  var source_container = document.getElementById('source-container');
  var source_image = document.getElementById('source-image');

  // { "app.yaml" : {
  //        "mime_type": "text/yaml",
  //        "contents" : "...",
  //        "dirty"    : false },
  //   "main.py" : {
  //        ...
  //   }
  // }
  var files = {};

  var _editor;
  var _output_window;
  var _popout = false;

  $scope.popout = function() {
    _popout = true;
    _output_window = undefined;
  }

  $scope.selectme = function(evt) {
    var elem = evt.srcElement;
    elem.focus();
    elem.select();
  }

  $scope.run = function() {
    // wait for pending saves to complete
    DoSerial.add(function() {
      var container = document.getElementById('output-container');
      if (_output_window && _output_window.closed) {
        _popout = false;
      }
      if (_popout) {
        container.style.display = 'none';
        _output_window = window.open($scope.config.project_run_url,
                                     $scope.config.project_id);
      } else {
        container.style.display = 'block';
        var iframe = document.getElementById('output-iframe');
        iframe.src = $scope.config.project_run_url;
      }
    });
  }

  function _save(path) {
    DoSerial.add(function() {
      var file = files[path];
      if (!file.dirty) {
        return;
      }
      file.dirty = false;
      $scope.filestatus = 'Saving ' + path + ' ...';
      return $http.put('putfile/' + encodeURI(path), file.contents, {
                       headers: {'Content-Type': 'text/plain; charset=utf-8'}
      })
      .success(function(data, status, headers, config) {
        $scope.filestatus = ''; // saved
      })
      .error(function(data, status, headers, config) {
        $log.warn('Save failed', path);
        file.dirty = true;
      }).then(function() {
        _saveDirtyFiles();
      });
    });
  }

  function _saveDirtyFiles() {
    for (var path in files) {
      if (!files[path].dirty) {
        continue;
      }
      var dirtypath = path;
      DoSerial.add(function() {
        _save(dirtypath);
      });
    }
  }

  // editor onChange
  function editorOnChange(from, to, text, next) {
     var file = files[$scope.currentPath];
     file.contents = _editor.getValue();
     file.dirty = true;
     _saveDirtyFiles();
  }

  $scope.prompt_file_delete = function() {
    var answer = prompt("Are you sure you want to delete " +
                        $scope.currentPath + "?\nType 'yes' to confirm.", "no");
    if (!answer || answer.toLowerCase()[0] != 'y') {
      return;
    }
    $scope.deletepath($scope.currentPath);
  }

  $scope.prompt_project_rename = function() {
    var new_project_name = prompt(
        'Enter a new name for this project',
        $scope.config.project_name);
    if (!new_project_name) {
      return;
    }
    DoSerial.add(function() {
      return $http.post('rename', {newname: new_project_name})
      .success(function(data, status, headers, config) {
        $scope.config.project_name = new_project_name;
      });
    });
  }

  $scope.prompt_file_rename = function() {
    var new_filename = prompt(
        'New filename?\n(You may specify a full path such as: foo/bar.txt)',
        $scope.currentPath);
    if (!new_filename) {
      return;
    }
    if (new_filename[0] == '/') {
      new_filename = new_filename.substr(1);
    }
    if (!new_filename || new_filename == $scope.currentPath) {
      return;
    }
    $scope.movefile($scope.currentPath, new_filename);
  }

  function hide_context_menus() {
    $scope.showfilecontextmenu = false;
    $scope.showprojectcontextmenu = false;
  }

  // setup context menu clear handler
  window.addEventListener('click', function(evt) {
    hide_context_menus();
    $scope.$apply();
  }, false);

  $scope.project_context_menu = function(evt) {
    evt.stopPropagation();
    hide_context_menus();
    $scope.showprojectcontextmenu = true;
    var menuDiv = document.getElementById('project-context-menu');
    menuDiv.style.left = evt.pageX + 'px';
    menuDiv.style.top = evt.pageY + 'px';
  };

  $scope.file_context_menu = function(evt, path) {
    evt.stopPropagation();
    hide_context_menus();
    $scope.select(path);
    $scope.showfilecontextmenu = true;
    var menuDiv = document.getElementById('file-context-menu');
    menuDiv.style.left = evt.pageX + 'px';
    menuDiv.style.top = evt.pageY + 'px';
  };

  $scope.orderFiles = function() {
    $scope.files = $filter('orderBy')($scope.files, 'name');
  };

  $scope.insertPath = function(path) {
    if (!(path in files)) {
      files[path] = {
          mime_type: 'text/plain',
          contents: '',
          dirty: false,
      };
      $scope.files.push({name: path});
      $scope.orderFiles();
    }
    $scope.select(path);
  };

  $scope.prompt_for_new_file = function() {
    var path = prompt('New filename?', '');
    if (!path) {
      return;
    }
    if (path[0] == '/') {
      path = path.substr(1)
    }

    $scope.insertPath(path);
  };

  $scope.deletepath = function(path) {
    DoSerial.add(function() {
      delete files[path];
      return $http.post('deletepath/' + encodeURI(path))
      .success(function(data, status, headers, config) {
        for (var i=0; i<$scope.files.length; i++) {
          if (path == $scope.files[i].name) {
            $scope.files.splice(i, 1);
            break;
          }
        }
        $scope.select($scope.files[0].name);
      });
    });
  };

  $scope.movefile = function(path, newpath) {
    DoSerial.add(function() {
      files[newpath] = files[path];
      delete files[path];
      for (var i=0; i<$scope.files.length; i++) {
        if (path == $scope.files[i].name) {
          $scope.files[i].name = newpath;
          break;
        }
      }
      return $http.post('movefile/' + encodeURI(path), {newpath: newpath})
      .success(function(data, status, headers, config) {
        $scope.currentPath = newpath;
        $scope.orderFiles();
      });
    });
  };

  function createEditor(mime_type) {
    return CodeMirror(source_code, {
      value: 'Initializing...',
      mode: mime_type,
      lineNumbers: true,
      matchBrackets: true,
      undoDepth: 440, // default = 40
    });
  }

  var noJsonTransform = function(data) { return data; };

  var _getfileurl = function(path) {
    return '//' + $scope.config.BLISS_USER_CONTENT_HOST +
           document.location.pathname + 'getfile/' +
           encodeURI(path);
  };

  var _get = function(path, success_cb) {
    if (files[path]) {
      success_cb();
      return;
    }
    var url = _getfileurl(path);
    $http.get(url, {transformResponse: noJsonTransform})
    .success(function(data, status, headers, config) {
      if (files[path]) {
        return;
      }
      // e.g. 'text/html; charset=UTF-8'
      var mime_type = headers('Content-Type');
      // Workaround missing HTTP response headers for CORS requests
      // See https://github.com/angular/angular.js/issues/1468
      // See https://bugzilla.mozilla.org/show_bug.cgi?id=608735
      if (!mime_type) {
        mime_type = 'application/octet-stream';
      }
      // strip '; charset=...'
      mime_type = mime_type.replace(/ ?;.*/, '');
      files[path] = {
          mime_type: mime_type,
          contents: data,
          dirty: false,
      };
      success_cb();
    });
  };

  $scope.select = function(path) {
    _get(path, function() {
      var file = files[path];
      if (/^image\//.test(file.mime_type)) {
        var url = _getfileurl(path);
        source_image.setAttribute('src', url);
        source_container.setAttribute('class', 'image');
      } else {
        while(source_code.hasChildNodes()) {
          source_code.removeChild(source_code.childNodes[0]);
        }
        _editor = createEditor(file.mime_type);
        _editor.getScrollerElement().id = 'scroller-element';
        source_container.setAttribute('class', 'code');
        _editor.setValue(file.contents);
        _editor.setOption('onChange', editorOnChange);
        _editor.focus();
      }
      $scope.currentPath = path;
    });
  };

  var listfiles = function() {
    return Files.query(function(files) {
      $scope.files = files;
      $scope.select($scope.files[0].name);
    });
  };

  var getconfig = function() {
    return $http.get('getconfig')
    .success(function(data, status, headers, config) {
       $scope.config = data;
    });
  };

  DoSerial.add(getconfig());
  DoSerial.add(listfiles());
  DoSerial.add(function() {
    resizer('divider1', 'source-container');
    resizer('divider2', 'output-iframe');
  });

}
