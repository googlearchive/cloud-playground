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

.factory('blissHttpInterceptor', function($q, $log) {
  return function(promise) {
    return promise.then(function(response) {
      return response;
    }, function(err) {
      if (err instanceof Error) {
        alert(err);
      } else if (err.headers('X-Bliss-Error')) {
        alert('Error:\n' + err.data);
      } else {
        $log.error('HTTP', err);
      }
      return $q.reject(err);
    });
  };
})

.factory('DoSerial', function($q, $log) {

  var deferred = $q.defer();
  deferred.resolve();
  var promise = deferred.promise;

  var DoSerial = {
    then: function(func) {
      promise = promise.then(function() {
        return func();
      }, function(err) {
        $log.error('DoSerial encountered', err);
        return func();
      });
      // allow chained calls, e.g. DoSerial.then(...).then(...)
      return DoSerial;
    }
  };
  return DoSerial;

});

function HeaderController($scope, $location) {

  $scope.alreadyhome = function() {
    return $location.path() == '/bliss/';
  }

}

function AdminController($scope, $http, $window, DoSerial) {

  $scope.big_red_button = function() {
    DoSerial
    .then(function() {
      return $http.post('nuke')
      .success(function(data, status, headers, config) {
        document.body.scrollTop = 0;
        $window.location.reload();
      });
    });
  };

}

function MainController($scope, $http, $location, $window, $log, DoSerial) {

  DoSerial
  .then(function() {
    return $http.get('getprojects')
    .success(function(data, status, headers, config) {
      $scope.projects = data;
    });
  })
  .then(function() {
    return $http.get('gettemplates')
    .success(function(data, status, headers, config) {
      $scope.templates = data;
    });
  })
  .then(function() {
    $scope.loaded = true;
  });

  $scope.login = function() {
    $window.location = '/bliss/login';
  }

  $scope.select_project = function(project) {
    $location.path('/bliss/p/' + project.key);
  }

  $scope.prompt_for_new_project = function(template) {
    return DoSerial
    .then(function() {
      return $http.post('createproject', {
          template_url: template.key,
          project_name: template.name,
          project_description: template.description})
      .success(function(data, status, headers, config) {
        $scope.projects.push(data);
        return;
      });
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
      // TODO figure out how we can modify $scope.projects directly
      // and force 'ng-show/ng-hide="projects"' to re-evaluated
      var projects = [];
      for (i in $scope.projects) {
        if ($scope.projects[i] != project) {
          projects.push($scope.projects[i]);
        }
      }
      $scope.projects = projects;
    });
  };

}

function ProjectController($scope, $http, $filter, $log, $timeout, DoSerial) {

  var source_code = document.getElementById('source-code');
  var source_container = document.getElementById('source-container');
  var source_image = document.getElementById('source-image');

  // { "app.yaml" : {
  //        "name"     : "app.yaml",
  //        "mime_type": "text/yaml",
  //        "contents" : "...",
  //        "dirty"    : false },
  //   "main.py" : {
  //        ...
  //   }
  // }
  $scope.files = {};

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
    return DoSerial
    .then(function() {
        _saveDirtyFiles();
    })
    .then(function() {
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
    return DoSerial
    .then(function() {
      var file = $scope.files[path];
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
        $scope.filestatus = 'Failed to save ' + path;
        $log.warn('Save failed', path);
        file.dirty = true;
      });
    });
  }

  function _saveDirtyFiles() {
    for (var path in $scope.files) {
      if (!$scope.files[path].dirty) {
        continue;
      }
      var dirtypath = path;
      DoSerial
      .then(function() {
        _save(dirtypath);
      })
      .then(function() {
        _saveDirtyFiles();
      });
    }
  }

  // editor onChange
  function editorOnChange(from, to, text, next) {
    $scope.$apply(function() {
      var file = $scope.files[$scope.currentPath];
      file.contents = _editor.getValue();
      if (file.dirty) {
        return;
      }
      file.dirty = true;
      $timeout(function() {
        _saveDirtyFiles();
      }, 1000);
    });
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
    DoSerial
    .then(function() {
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

  $scope.insertPath = function(path) {
    if (!(path in $scope.files)) {
      $scope.files[path] = {
          name: path,
          mime_type: 'text/plain',
          contents: '',
          dirty: false,
      };
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

  function _selectFirstFile() {
    for (path in $scope.files) {
      $scope.select(path);
      break;
    }
  }

  $scope.deletepath = function(path) {
    DoSerial
    .then(function() {
      delete $scope.files[path];
      return $http.post('deletepath/' + encodeURI(path))
      .success(function(data, status, headers, config) {
        _selectFirstFile();
      });
    });
  };

  $scope.movefile = function(path, newpath) {
    DoSerial
    .then(function() {
      $scope.files[newpath] = $scope.files[path];
      $scope.files[newpath].name = newpath;
      delete $scope.files[path];
      return $http.post('movefile/' + encodeURI(path), {newpath: newpath})
      .success(function(data, status, headers, config) {
        $scope.currentPath = newpath;
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
    if ($scope.files[path].hasOwnProperty('contents')) {
      success_cb();
      return;
    }
    var url = _getfileurl(path);
    $http.get(url, {transformResponse: noJsonTransform})
    .success(function(data, status, headers, config) {
      $scope.files[path].contents = data;
      $scope.files[path].dirty = false;
      success_cb();
    });
  };

  $scope.select = function(path) {
    var file = $scope.files[path];
    if (/^image\//.test(file.mime_type)) {
      var url = _getfileurl(path);
      source_image.setAttribute('src', url);
      source_container.setAttribute('class', 'image');
      $scope.currentPath = path;
      return;
    }
    _get(path, function() {
      while(source_code.hasChildNodes()) {
        source_code.removeChild(source_code.childNodes[0]);
      }
      _editor = createEditor(file.mime_type);
      _editor.getScrollerElement().id = 'scroller-element';
      source_container.setAttribute('class', 'code');
      _editor.setValue(file.contents);
      _editor.setOption('onChange', editorOnChange);
      _editor.focus();
      $scope.currentPath = path;
    });
  };

  var listfiles = function() {
    return $http.get('listfiles')
    .success(function(data, status, headers, config) {
      angular.forEach(data, function(props, i) {
        $scope.files[props.name] =  props;
      });
      _selectFirstFile();
    });
  };

  var getconfig = function() {
    return $http.get('getconfig')
    .success(function(data, status, headers, config) {
       $scope.config = data;
    });
  };

  DoSerial
  .then(getconfig)
  .then(listfiles)
  .then(function() {
    resizer('divider1', 'source-container');
    resizer('divider2', 'output-iframe');
  });

}
