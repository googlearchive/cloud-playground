'use strict';

/* Controllers */

// TODO: test
function AlertController($scope, Alert) {

  Alert.note('Note: This is a shared public playground.' +
             ' Anyone can read, modify or delete your projects,' +
             ' files and data at any time. Your private source' +
             ' code and data are not safe here.');

  $scope.alerts = Alert.alerts;

  $scope.closeAlert = function(idx) {
    Alert.remove_alert(idx);
  };

}

function HeaderController($scope, $location) {

  $scope.alreadyhome = function() {
    return $location.path() == '/playground/';
  };

}

// TODO: test
function RenameProjectController($scope, $log, dialog, project_name) {

  $scope.project_name = project_name;

  $scope.close = function(project_name) {
    dialog.close(project_name);
  };

}

function PageController($scope, $http, DoSerial, $routeParams, $window,
                        $dialog, $location, $log, WindowService) {

  function getconfig() {
    $scope.status = 'Retrieving configuration';
    return $http.get('/playground/getconfig')
    .success(function(data, status, headers, config) {
       $scope.config = data;
    });
  };

  $scope.getproject = function() {
      $scope.status = 'Retrieving project ' + project_id;
      var project_id = $scope.namespace();
      return $http.get('/playground/p/' + project_id + '/getproject')
      .success(function(data, status, headers, config) {
          $scope.projects.push(data);
      });
  };

  function getprojects() {
    $scope.status = 'Retrieving user projects';
    return $http.get('/playground/getprojects')
    .success(function(data, status, headers, config) {
      $scope.projects = data;
    });
  }

  function get_template_projects() {
    $scope.status = 'Retrieving template projects';
    return $http.get('/playground/gettemplateprojects')
    .success(function(data, status, headers, config) {
      $scope.template_projects = data;
    });
  }

  DoSerial
  .then(getconfig)
  .then(get_template_projects)
  .then(getprojects);

  $scope.namespace = function() {
    return $routeParams.project_id ||
           ($scope.config && $scope.config.playground_namespace);
  };

  $scope.datastore_admin = function() {
    WindowService.open('/playground/datastore/' + $scope.namespace(), '_blank');
  };

  $scope.memcache_admin = function() {
    WindowService.open('/playground/memcache/' + $scope.namespace(), '_blank');
  };

  $scope.big_red_button = function() {
    DoSerial
    .then(function() {
      return $http.post('/playground/nuke')
      .success(function(data, status, headers, config) {
        WindowService.reload();
      });
    });
  };

  // TODO: test
  function prompt_oauth2_admin(credential) {
    $dialog.dialog({
        controller: 'OAuth2AdminController',
        templateUrl: '/playground/oauth2_admin.html',
        resolve: {
            key: credential.key,
            url: credential.url,
            client_id: credential.client_id,
            client_secret: credential.client_secret,
        },
    })
    .open().then(function(credential) {
      $http.post('/playground/oauth2_admin', credential);
    });
  }

  // TODO: test
  $scope.oauth2_admin = function(key, url) {
    $http.post('/playground/oauth2_admin', {key: key, url: url})
    .success(function(data, status, headers, config) {
      prompt_oauth2_admin(data);
    });
  };

  $scope.has_projects = function() {
    for (var i in $scope.projects) {
      return true;
    }
    return false;
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
  };

  $scope.delete_project = function(project) {
    $scope.project = undefined;
    $http.post('/playground/p/' + encodeURI(project.key) + '/delete')
    .success(function(data, status, headers, config) {
      for (var i in $scope.projects) {
        if ($scope.projects[i] == project) {
          $scope.projects.splice(i, 1);
          break;
        }
      }
      for (var i in $scope.template_projects) {
        if ($scope.template_projects[i] == project) {
          $scope.template_projects.splice(i, 1);
          break;
        }
      }
      $location.path('/playground/');
    });
  };

  $scope.prompt_delete_project = function(project) {
    var title = 'Confirm project deletion';
    var msg = 'Are you sure you want to delete project "' + project.name +
              '"?';
    var btns = [{result: false, label: 'Cancel'},
                {result: true, label: 'DELETE PROJECT',
                 cssClass: 'btn-primary btn-danger'}];
    // TODO: autofocus primary button
    $dialog.messageBox(title, msg, btns)
    .open()
    .then(function(result) {
      if (result) {
        $scope.delete_project(project);
      }
    });
  };

  $scope.set_loaded = function() {
    $scope.loaded = true;
  }

}

function MainController($scope, $http, $window, $location, $log, $routeParams,
                        $q, Alert, DoSerial) {

  // TODO: test
  function by_template_url(template_url, projects) {
    var results = [];
    for (var i in projects) {
      if (projects[i].template_url == template_url) {
        results.push(projects[i]);
      }
    }
    return results;
  }

  // TODO: test
  $scope.new_project_by_url = function(repo_url) {
    var deferred = $q.defer();
    for (var i in $scope.template_projects) {
      if ($scope.template_projects[i].template_url == repo_url) {
        throw 'Template already exists';
      }
    }
    DoSerial
    .then(function() {
      var data = {
        'name': '(Creating template project...)',
        'description': '(Please wait...)',
        'in_pogress_task_name': 'foo',
      };
      $scope.template_projects.push(data);
    })
    DoSerial
    .then(function() {
      return $http.post('/playground/create_template_project_by_url', {
          repo_url: repo_url,
      })
      .success(function(data, status, headers, config) {
        $scope.template_projects.pop();
        $scope.template_projects.push(data);
        deferred.resolve();
      })
      .error(function(data, status, headers, config) {
        $scope.template_projects.pop();
        deferred.reject('Failed to create template project due to HTTP error ' +
                        status + ' ' + data);
      });
    });
    return deferred.promise;
  };

  // TODO: test
  function create_project_from_template(template_url) {
    var deferred = $q.defer();

    var user_projects = by_template_url(template_url, $scope.projects);
    var template_projects = by_template_url(template_url,
                                            $scope.template_projects);

    if (user_projects.length == 1) {
      $scope.status = 'Opening project';
      Alert.info('Found an existing project based on the requested template');
      $scope.select_project(user_projects[0]);
      deferred.resolve();
      return deferred.promise;
    }

    if (user_projects.length > 1) {
      Alert.info('You have ' + user_projects.length +
                 ' projects based on the requested template');
      // TODO: make these assignments work
      //$scope.projects = user_projects;
      //$scope.template_projects = template_projects;
      deferred.resolve();
      return deferred.promise;
    }

    if (template_projects.length == 0) {
      $scope.status = 'Creating new template project based on ' + template_url;
      deferred.resolve();
      deferred.promise
      .then(function() {
        return $scope.new_project_by_url(template_url);
      });
      return deferred.promise;
    }

    if (template_projects.length > 1) {
      // TODO: investigate using deferred.reject() instead of 'throw'
      throw 'Found ' + template_projects.length +
            ' template projects with template URL ' + template_url;
    }

    deferred.promise
    .then(function() {
      $scope.status = 'Cloning project from template ' + template_url;
      return $scope.new_project(template_projects[0]);
    })
    .then(function() {
      var user_projects = by_template_url(template_url, $scope.projects);
      if (user_projects.length != 1) {
        throw 'Unexpectedly found ' + user_projects.length +
              ' projects with template URL ' + template_url;
      }
      $scope.select_project(user_projects[0]);
    });
    deferred.resolve();
    return deferred.promise;
  }

  // TODO: test
  DoSerial
  .then(function() {
    var template_url = $routeParams.template_url;
    if (template_url) {
      $location.search({});
      return create_project_from_template(template_url);
    }
  })
  .then($scope.set_loaded);

  $scope.login = function() {
    $window.location.replace('/playground/login');
  };

  // TODO: test
  $scope.recreate_template_project = function(template_project) {
    template_project.in_progress_task_name = 'foo'
    DoSerial
    .then(function() {
      return $http.post('/playground/recreate_template_project', {
          project_id: template_project.key,
      });
    });
  };

  $scope.new_project = function(template_project) {
    var deferred = $q.defer();
    var data = {
      'name': '(Creating project...)',
      'description': '(Please wait and then refresh this page.)',
    };
    $scope.projects.push(data);
    $http.post('/playground/copyproject', {
        project_id: template_project.key,
    })
    .success(function(data, status, headers, config) {
      $scope.projects.pop();
      $scope.projects.push(data);
      deferred.resolve();
    })
    .error(function(data, status, headers, config) {
      $scope.projects.pop();
      deferred.reject('Failed to copy project due to HTTP error ' +
                      status + ' ' + data);
    });
    return deferred.promise;
  };

}

// TODO: test
function NewFileController($scope, $log, dialog, path) {

  $scope.path = path;

  $scope.close = function(path) {
    dialog.close(path);
  };

}

// TODO: test
function RenameFileController($scope, $log, dialog, path) {

  $scope.path = path;

  $scope.close = function(path) {
    dialog.close(path);
  };

}

// TODO: test
function OAuth2AdminController($scope, $log, dialog, key, url, client_id,
                               client_secret) {

  $scope.key = key;
  $scope.url = url;
  $scope.client_id = client_id;
  $scope.client_secret = client_secret;

  $scope.close = function(client_id, client_secret) {
    dialog.close({key: key, url: url, client_id: client_id,
                  client_secret: client_secret});
  };

}

function ProjectController($scope, $browser, $http, $routeParams, $window,
                           $dialog, $location, $log, DoSerial, DomElementById,
                           WrappedElementById, Backoff) {

  // keep in sync with appengine_config.py
  var MIMIC_PROJECT_ID_QUERY_PARAM = '_mimic_project';

  // TODO: remove; don't maintain DOM references
  var _output_window;

  // TODO: remove; don't maintain DOM references
  var _popout = false;

  // TODO: remove once file contents are returned in JSON response
  $scope.no_json_transform = function(data) { return data; };

  function toquerystring(params) {
      var qs = '';
      angular.forEach(params, function(value, key) {
          qs += '&' + encodeURIComponent(key) + '=' + encodeURIComponent(value);
      });
      return qs.replace('&', '?');
  }

  $scope.url_of = function(control_path, params) {
    var p = {};
    p[MIMIC_PROJECT_ID_QUERY_PARAM] = $scope.project.key;
    angular.extend(p, params);
    var qs = toquerystring(p);
    return '//' + $scope.config.PLAYGROUND_USER_CONTENT_HOST +
           '/_ah/mimic/' + control_path + qs;
  };

  $scope.image_url_of = function(file) {
    return (file && $scope.is_image_mime_type(file.mime_type)) ?
        $scope.url_of('file', {path: file.path}) : '';
  };

  // TODO: this.foo = function() {...} // for testability
  $scope._get = function(file, success_cb) {
    if (file.hasOwnProperty('contents')) {
      success_cb();
      return;
    }
    var url = $scope.url_of('file', {path: file.path});
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
    var url = $scope.url_of('dir', {});
    return $http.get(url)
    .success(function(data, status, headers, config) {
      $scope.files = {};
      angular.forEach(data, function(props, i) {
        $scope.files[props.path] = props;
      });
    });
  };

  // TODO: test
  function _save(path) {
    var file = $scope.files[path];
    if (!file.dirty) {
      return;
    }
    file.dirty = false;
    $scope.filestatus = 'Saving ' + path + ' ...';
    var url = $scope.url_of('file', {path: file.path});
    return $http.put(url, file.contents, {
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
      Backoff.schedule(_save_dirty_files);
    });
  }

  // TODO: test
  function _save_dirty_files() {
    for (var path in $scope.files) {
      if ($scope.files[path].dirty) {
        var dirtypath = path;
        DoSerial
        .then(function() {
          return _save(dirtypath);
        });
        break;
      }
    }
  }

  // TODO: test
  $scope.create_on_change_closure = function(file) {
    return function(instance, changeObj) {
      if (file.dirty) {
        return;
      }
      file.dirty = true;
      $scope.$apply(); // need to apply here for dirty mark
      Backoff.schedule(_save_dirty_files);
    };
  }

  $scope.select_file = function(file) {
    $location.hash(file.path);
    if ($scope.is_image_mime_type(file.mime_type)) {
      $scope.current_file = file;
      return;
    }
    $scope._get(file, function() {
      $scope.current_file = file;
    });
  };

  $scope.set_path = function(path) {
    $location.hash(path);
  }

  $scope._select_a_file = function() {
    var path = $location.hash();
    var file = $scope.files[path];
    if (file) {
      $scope.select_file(file);
      return;
    }
    // select first file
    for (var path in $scope.files) {
      $scope.select_file($scope.files[path]);
      break;
    }
  };

  function setcurrentproject() {
      for (var i in $scope.projects) {
          if ($scope.projects[i].key == $routeParams.project_id) {
              $scope.project = $scope.projects[i];
              return true;
          }
      }
      return false;
  }

  DoSerial
  .then(function() {
    if (!setcurrentproject()) {
      // project_id is not in $scope.projects
      return $scope.getproject()
      .then(setcurrentproject);
    }
  })
  .then($scope._list_files)
  .then($scope._select_a_file);

  // TODO: test
  $scope.insert_path = function(path) {
    var file = $scope.files[path];
    if (!file) {
      // Create a file on the server side and use the result.
      $http.put($scope.url_of('file', {path: path}), '', {
        headers: {'Content-Type': 'text/plain; charset=utf-8'}
      })
      .success(function(data, status, header, config) {
        $scope.files[path] = data;
        $scope.select_file(data);
      })
      .error(function(data, status, header, config) {
        // Note: If the mimic encounters an unhandled exception like
        // DeadlineExceededError, the response doesn't have a CORS
        // header under the current implementation, so that the status
        // here just becomes 0.
        throw Error('Failed to create a new file with a status code: ' +
                    status + '.');
      });
    } else {
      $scope.select_file(file);
    }
  };

  // TODO: test
  $scope.prompt_new_file = function() {
    $dialog.dialog({
        controller: 'NewFileController',
        templateUrl: '/playground/new_file_modal.html',
        resolve: {path: ''},
    })
    .open().then(function(path) {
      if (path) {
        // remove leading and trailing slash(es)
        path = path.replace(/^\/*(.*?)\/*$/, '$1');
        $scope.insert_path(path);
      }
    });
  };

  // TODO: remove
  function hide_context_menus() {
    $scope.showfilecontextmenu = false;
    $scope.showprojectcontextmenu = false;
  }

  // TODO: remove
  window.addEventListener('click', function(evt) {
    hide_context_menus();
    $scope.$apply();
  }, false);

  // TODO: test
  // TODO: replace with $dialog
  $scope.project_context_menu = function(evt) {
    evt.stopPropagation();
    hide_context_menus();
    $scope.showprojectcontextmenu = true;
    $scope.project_context_menu_pos = [evt.pageX, evt.pageY];
  };

  // TODO: test
  function project_rename(project, name) {
    DoSerial
    .then(function() {
      return $http.post('rename', {newname: name})
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

  // TODO: test
  $scope.prompt_project_rename = function(project) {
    $dialog.dialog({
        controller: 'RenameProjectController',
        templateUrl: '/playground/rename_project_modal.html',
        resolve: {project_name: project.name},
    })
    .open().then(function(name) {
      if (name) {
        project_rename(project, name);
      }
    });
  };

  // TODO: test
  $scope.file_context_menu = function(evt, file) {
    evt.stopPropagation();
    hide_context_menus();
    $scope.select_file(file);
    $scope.showfilecontextmenu = true;
    $scope.file_context_menu_pos = [evt.pageX, evt.pageY];
  };

  // TODO: test
  function delete_file(file) {
    DoSerial
    .then(function() {
      var url = $scope.url_of('delete', {path: file.path});
      return $http.post(url)
      .success(function(data, status, headers, config) {
        delete $scope.files[file.path];
        $scope._select_a_file();
      });
    });
  };

  // TODO: test
  $scope.prompt_delete_file = function(file) {
    var title = 'Confirm file deletion';
    var msg = 'Are you sure you want to delete file "' +
              $scope.current_file.path + '"?';
    var btns = [{result: false, label: 'Cancel'},
                {result: true, label: 'DELETE FILE',
                 cssClass: 'btn-primary btn-danger'}];
    // TODO: autofocus primary button
    $dialog.messageBox(title, msg, btns)
    .open()
    .then(function(result) {
      if (result) {
        delete_file(file);
      }
    });
  };

  // TODO: test
  function file_rename(file, path) {
    if (!path || path == file.path) {
      return;
    }
    DoSerial
    .then(function() {
      var oldpath = file.path;
      var url = $scope.url_of('move', {path: file.path, newpath: path});
      return $http.post(url)
      .success(function(data, status, headers, config) {
        delete $scope.files[oldpath];
        file.path = path;
        $scope.files[path] = file;
        // TODO: have server send updated MIME type
        $scope.current_file = file;
      });
    });
  };

  // TODO: test
  $scope.prompt_file_rename = function(file) {
    $dialog.dialog({
        controller: 'RenameFileController',
        templateUrl: '/playground/rename_file_modal.html',
        resolve: {path: file.path},
    })
    .open().then(function(path) {
      if (!path) {
        return;
      }
      while (path[0] == '/') {
        path = path.substr(1);
      }
      file_rename(file, path);
    });
  };

  // TODO: test
  $scope.popout = function() {
    _popout = true;
    _output_window = undefined;
  };

  // TODO: test
  $scope.select_me = function(evt) {
    var elem = evt.srcElement;
    elem.focus();
    elem.select();
  };

  // TODO: test
  $scope.run = function() {
    return DoSerial
    .then(function() {
      _save_dirty_files();
    })
    .then(function() {
      // TODO: try to avoid DOM access
      var container = WrappedElementById('output-container');
      if (_output_window && _output_window.closed) {
        _popout = false;
      }
      if (_popout) {
        container.addClass('hidden');
        // TODO: create open window service (so we can test)
        // TODO: read https://github.com/vojtajina/ng-directive-testing
        _output_window = window.open($scope.project.run_url,
                                     $scope.project.key);
      } else {
        container.removeClass('hidden');
        var iframe = WrappedElementById('output-iframe');
        iframe.attr('src', $scope.project.run_url);
      }
    });
  };

}
