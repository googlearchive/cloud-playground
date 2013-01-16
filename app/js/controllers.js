'use strict';

/* Controllers */

function HeaderController($scope, $location) {

  $scope.alreadyhome = function() {
    return $location.path() == '/playground/';
  }

}

function PageController($scope, $http, DoSerial, $routeParams, $window) {

  function getconfig() {
    return $http.get('/playground/getconfig')
    .success(function(data, status, headers, config) {
       $scope.config = data;
    });
  };

  function getprojects() {
    return $http.get('/playground/getprojects')
    .success(function(data, status, headers, config) {
      $scope.projects = data;
    });
  };

  DoSerial
  .then(getconfig)
  .then(getprojects)

  $scope.namespace = function() {
    return $routeParams.project_id ||
           ($scope.config && $scope.config.playground_namespace);
  };

  // TODO: determine if there's a better way
  $scope.datastore_admin = function() {
    $window.open('/playground/datastore/' + $scope.namespace(), '_blank');
  };

  // TODO: determine if there's a better way
  $scope.memcache_admin = function() {
    $window.open('/playground/memcache/' + $scope.namespace(), '_blank');
  };

}

function MainController($scope, $http, $window, $location, DoSerial) {

  DoSerial
  .then(function() {
    return $http.get('/playground/gettemplates')
    .success(function(data, status, headers, config) {
      $scope.templates = data;
    });
  })
  .then(function() {
    $scope.loaded = true;
  });

  $scope.login = function() {
    $window.location.replace('/playground/login');
  }

  $scope.new_project = function(template) {
    DoSerial
    .then(function() {
      var data = {
        'name': '(Creating project...)',
        'description': '(Please wait...)',
      };
      $scope.projects.push(data);
    })
    .then(function() {
      return $http.post('/playground/createproject', {
          template_url: template.key,
          project_name: template.name,
          project_description: template.description})
      .success(function(data, status, headers, config) {
        $scope.projects.pop();
        $scope.projects.push(data);
      });
    });
  };

  $scope.select_project = function(project) {
    DoSerial
    .then(function() {
      return $http.post('/playground/p/' + project.key + '/touch')
      .success(function(data, status, headers, config) {
        for (var i in $scope.projects) {
          if ($scope.projects[i] == project) {
            $scope.projects[i] = project = data;
            break;
          }
        }
        $location.path('/playground/p/' + project.key);
      });
    });
  }

}

function ProjectController($scope, $browser, $http, $routeParams, $window,
                           DoSerial, DomElementById) {

  // TODO: remove once file contents are returned in JSON response
  $scope.no_json_transform = function(data) { return data; };

  $scope.url_of = function(file) {
    return '//' + $scope.config.PLAYGROUND_USER_CONTENT_HOST +
           $window.location.pathname + 'getfile/' +
           encodeURI(file.name);
  };

  $scope.image_url_of = function(file) {
    return (file && $scope.is_image_mime_type(file.mime_type)) ?
        $scope.url_of(file) : '';
  };

  // TODO: don't expose function on $scope, while retaining testability
  $scope._get = function(file, success_cb) {
    if (file.hasOwnProperty('contents')) {
      success_cb();
      return;
    }
    var url = $scope.url_of(file);
    $http.get(url, {transformResponse: $scope.no_json_transform})
    .success(function(data, status, headers, config) {
      file.contents = data;
      file.dirty = false;
      success_cb();
    });
  };

  $scope.is_image_mime_type = function(mime_type) {
    return /^image\//.test(mime_type);
  };

  $scope._list_files = function() {
    // Workaround https://github.com/angular/angular.js/issues/1761
    var url = $browser.url() + 'listfiles';
    return $http.get(url)
    .success(function(data, status, headers, config) {
      $scope.files = {};
      angular.forEach(data, function(props, i) {
        $scope.files[props.name] = props;
      });
    });
  };

  $scope.editorOnChange = function(from, to, text, next) {
/*
    $scope.$apply(function() {
      $scope.current_file.contents = $scope._editor.getValue();
      if ($scope.current_file.dirty) {
        return;
      }
      $scope.current_file.dirty = true;
      Backoff.schedule(_saveDirtyFiles);
    });
*/
  };

  // TODO: consider replacing DOM maniupulation here with a directive
  $scope.create_editor = function(mime_type) {
    if ($scope._editor) {
      angular.element($scope._editor.getWrapperElement()).remove();
    }
    $scope._editor = $window.CodeMirror(DomElementById('source-code'), {
      mode: mime_type,
      lineNumbers: true,
      matchBrackets: true,
      undoDepth: 440, // default = 40
    });
    //$scope._editor.getScrollerElement().id = 'scroller-element';
    $scope._editor.setValue($scope.current_file.contents);
    $scope._editor.setOption('onChange', $scope.editorOnChange);
    $scope._editor.focus();
  }


  $scope.select_file = function(file) {
    if ($scope.is_image_mime_type(file.mime_type)) {
      $scope.current_file = file;
      return;
    }
    $scope._get(file, function() {
      return DoSerial
      .then(function() {
        $scope.current_file = file;
      })
      .tick() // needed when switching from source-image to editor
      .then(function() {
        $scope.create_editor(file.mime_type);
      });
    });
  };

  $scope._select_first_file = function() {
    for (var path in $scope.files) {
      $scope.select_file($scope.files[path]);
      break;
    }
  }

  DoSerial
  .then(function() {
    for (var i in $scope.projects) {
      if ($scope.projects[i].key == $routeParams.project_id) {
        $scope.project = $scope.projects[i];
        break;
      }
    }
  })
  .then($scope._list_files)
  .then($scope._select_first_file);

}

/*

function PageController($scope, $http, $location, $routeParams, $window,
                        DoSerial, LightBox) {

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

  // TODO: don't use prompt()
  $scope.prompt_to_delete_project = function(project) {
    var answer = prompt("Are you sure you want to delete project " +
                        project.name + "?\nType 'yes' to confirm.", "no");
    if (!answer || answer.toLowerCase()[0] != 'y') {
      return;
    }
    $scope.project = undefined;
    $http.post('/playground/p/' + encodeURI(project.key) + '/delete')
    .success(function(data, status, headers, config) {
      for (var i in $scope.projects) {
        if ($scope.projects[i] == project) {
          $scope.projects.splice(i, 1);
          break;
        }
      }
      $location.path('/playground/');
    });
  };

  $scope.hasprojects = function() {
    for (var i in $scope.projects) {
      return true;
    }
    return false;
  };

}

function LightboxController($scope, $window) {

  // TODO: determine if there's a better way
  $scope.reload = function() {
    $window.location.reload();
  };

  $scope.dismiss = function() {
    $scope.lightboxes.pop();
  };

}

function ProjectController($scope, $http, $filter, $log, $timeout, $routeParams,
                           Backoff, DoSerial, DomElementById,
                           WrappedElementById) {

  // TODO: determine if there's a better way
  var source_image = WrappedElementById('source-image');

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
      // TODO: try to avoid DOM access
      var container = WrappedElementById('output-container');
      if (_output_window && _output_window.closed) {
        _popout = false;
      }
      if (_popout) {
        container.addClass('hidden');
        _output_window = window.open($scope.project.run_url,
                                     $scope.project.key);
      } else {
        container.removeClass('hidden');
        var iframe = WrappedElementById('output-iframe');
        iframe.attr('src', $scope.project.run_url);
      }
    });
  }

  function _save(path) {
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
      Backoff.reset();
    })
    .error(function(data, status, headers, config) {
      $scope.filestatus = 'Failed to save ' + path;
      file.dirty = true;
      // implement seconds() function
      var secs = Backoff.backoff() / 1000;
      $log.warn(path, 'failed to save; will retry in', secs, 'secs');
      Backoff.schedule(_saveDirtyFiles);
    });
  }

  function _saveDirtyFiles() {
    for (var path in $scope.files) {
      if ($scope.files[path].dirty) {
        var dirtypath = path;
        DoSerial
        .then(function() {
          return _save(dirtypath);
        })
        break;
      }
    }
  }

  // TODO: don't use prompt()
  $scope.prompt_file_delete = function() {
    var answer = prompt("Are you sure you want to delete " +
                        $scope.current_file.name + "?\nType 'yes' to confirm.",
                        "no");
    if (!answer || answer.toLowerCase()[0] != 'y') {
      return;
    }
    $scope.deletefile($scope.current_file);
  }

  // TODO: don't use prompt()
  $scope.prompt_project_rename = function(project) {
    var new_project_name = prompt('Enter a new name for this project',
                                  project.name);
    if (!new_project_name) {
      return;
    }
    DoSerial
    .then(function() {
      return $http.post('rename', {newname: new_project_name})
      .success(function(data, status, headers, config) {
        for (var i in $scope.projects) {
          if ($scope.projects[i] == project) {
            $scope.project = $scope.projects[i] = data;
            break;
          }
        }
      });
    });
  }

  // TODO: don't use prompt()
  $scope.prompt_file_rename = function() {
    var new_filename = prompt(
        'New filename?\n(You may specify a full path such as: foo/bar.txt)',
        $scope.current_file.name);
    if (!new_filename) {
      return;
    }
    if (new_filename[0] == '/') {
      new_filename = new_filename.substr(1);
    }
    if (!new_filename || new_filename == $scope.current_file.name) {
      return;
    }
    $scope.movefile($scope.current_file, new_filename);
  }

  // TODO: determine if there's a better way
  function hide_context_menus() {
    $scope.showfilecontextmenu = false;
    $scope.showprojectcontextmenu = false;
  }

  // setup context menu clear handler
  // TODO: use $window rather than window
  window.addEventListener('click', function(evt) {
    hide_context_menus();
    $scope.$apply();
  }, false);

  // TODO: avoid DOM access
  $scope.project_context_menu = function(evt) {
    evt.stopPropagation();
    hide_context_menus();
    $scope.showprojectcontextmenu = true;
    var menuDiv = WrappedElementById('project-context-menu');
    menuDiv.css('left', evt.pageX + 'px');
    menuDiv.css('top', evt.pageY + 'px');
  };

  // TODO: avoid DOM access
  $scope.file_context_menu = function(evt, file) {
    evt.stopPropagation();
    hide_context_menus();
    $scope.select_file(file);
    $scope.showfilecontextmenu = true;
    var menuDiv = WrappedElementById('file-context-menu');
    menuDiv.css('left', evt.pageX + 'px');
    menuDiv.css('top', evt.pageY + 'px');
  };

  $scope.insertPath = function(path) {
    var file = $scope.files[path];
    if (!file) {
      file = {
          name: path,
          mime_type: 'text/plain',
          contents: '',
          dirty: false,
      };
      $scope.files[path] = file;
    }
    $scope.select_file(file);
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

  $scope.deletefile = function(file) {
    DoSerial
    .then(function() {
      return $http.post('deletepath/' + encodeURI(file.name))
      .success(function(data, status, headers, config) {
        delete $scope.files[file.name];
        $scope._select_first_file();
      });
    });
  };

  $scope.movefile = function(file, newpath) {
    DoSerial
    .then(function() {
      var oldpath = file.name;
      $scope.files[newpath] = file;
      $scope.files[newpath].name = newpath;
      delete $scope.files[oldpath];
      return $http.post('movefile/' + encodeURI(oldpath), {newpath: newpath})
      .success(function(data, status, headers, config) {
        $scope.current_file = file;
      });
    });
  };

}
*/
