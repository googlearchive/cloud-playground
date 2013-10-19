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

  $scope.cookie_problem = function() {
    return Alert.cookie_problem();
  }
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
                        $dialog, $location, $log, WindowService,
                        IframedDetector, ConfirmDialog) {

  DoSerial
  .then(getconfig)
  .then(getprojects);
  
  function getconfig() {
    $scope.status = 'Retrieving configuration';
    return $http.get('/playground/getconfig')
    .success(function(data, status, headers, config) {
       $scope.config = data;
    });
  };

  $scope.retrieveproject = function() {
      $scope.status = 'Retrieving project ' + project_id;
      var project_id = $scope.namespace();
      return $http.get('/playground/p/' + encodeURI(project_id) + '/retrieve')
      .success(function(data, status, headers, config) {
          $scope.projects.push(data);
      });
  };

  function getprojects() {
    $scope.status = 'Retrieving projects';
    return $http.get('/playground/getprojects')
    .success(function(data, status, headers, config) {
      $scope.projects = data;
    });
  }

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

  $scope.reload = function() {
    WindowService.reload();
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

  $scope.select_project = function(project) {
    $location.path('/playground/p/' + encodeURI(project.key));
    // remove template_url and other query parameters
    $location.search({});
  };

  $scope.delete_project = function(project) {
    $scope.project = undefined;
    for (var i in $scope.projects) {
      if ($scope.projects[i] == project) {
        $scope.projects.splice(i, 1);
        break;
      }
    }
    $http.post('/playground/p/' + encodeURI(project.key) + '/delete')
    .success(function(data, status, headers, config) {
      $location.path('/playground/');
    });
  };

  $scope.prompt_delete_project = function(project) {
    var title = 'Confirm project deletion';
    var msg = 'Are you sure you want to delete project "' + project.name +
              '"?';
    var okButtonText = 'DELETE PROJECT';
    var okButtonClass = 'btn btn-danger';
    var callback = function() {
      $scope.delete_project(project);
    }

    ConfirmDialog(title, msg, okButtonText, okButtonClass, callback);
  };

  $scope.set_loaded = function() {
    $scope.loaded = true;
  }

}

function MainController($scope, $http, $window, $location, $log, $routeParams,
                        $q, Alert, DoSerial) {

  // TODO: test
  DoSerial
  .then(function() {
    var template_url = $routeParams.template_url;
    if (template_url) {
      var expiration_seconds = parseInt($routeParams.expiration_seconds);
      return $scope.new_project_from_template_url(template_url, expiration_seconds)
      .catch(function() {
        $scope.set_loaded();
      });
    } else {
      $scope.set_loaded();
    }
  });

  // TODO: test
  $scope.new_project_from_template_url = function(repo_url, expiration_seconds) {
    var deferred = $q.defer();
    DoSerial
    .then(function() {
      $http.post('/playground/new_project_from_template_url', {
          repo_url: repo_url
      })
      .success(function(data, status, headers, config) {
        var project = data;
        $scope.projects.push(project);
        $scope.select_project(project);
        deferred.resolve();
      })
      .error(function(data, status, headers, config) {
        if (status == 408) {
          Alert.error(data);
        }
        deferred.reject('Failed to create project due to HTTP error ' +
                        status + ' ' + data);
      });
    });
    return deferred.promise;
  };

  // TODO: test
  $scope.create_template_project_by_url = function(repo_url) {
    var deferred = $q.defer();
    DoSerial
    .then(function() {
      var data = {
        'name': '(Creating template project...)',
        'description': '(Please wait...)',
        'in_pogress_task_name': 'foo',
        'orderby': '3',
      };
      $scope.projects.push(data);
      $http.post('/playground/create_template_project_by_url', {
          repo_url: repo_url
      })
      .success(function(data, status, headers, config) {
        $scope.projects.pop();
        for (var i in $scope.projects) {
          if ($scope.projects[i].key == data.key) {
            $scope.projects.splice(i, 1);
            break;
          }
        }
        $scope.projects.push(data);
        deferred.resolve();
      })
      .error(function(data, status, headers, config) {
        $scope.projects.pop();
        if (status == 408) {
          Alert.error(data);
          deferred.resolve();
        } else {
          deferred.reject('Failed to create template project due to HTTP error ' +
                          status + ' ' + data);
        }
      });
      return deferred.promise;
    });
  };

  $scope.login = function() {
    $window.location.replace('/playground/login');
  };

  // TODO: test
  $scope.recreate_template_project = function(template_project) {
    template_project.in_progress_task_name = 'foo'
    DoSerial
    .then(function() {
      return $http.post('/playground/recreate_template_project', {
          project_id: template_project.key
      });
    });
  };

  $scope.new_project = function(template_project, expiration_seconds) {
    var deferred = $q.defer();
    var data = {
      'name': '(Creating project...)',
      'description': '(Please wait and then refresh this page.)',
      'orderby': '3',
    };
    $scope.projects.push(data);
    $http.post('/playground/p/' + encodeURI(template_project.key) + '/copy', {
      'expiration_seconds': expiration_seconds
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

function ProjectController($scope, $browser, $http, $routeParams, $window, $sce,
                           $dialog, $location, $log, DoSerial, DomElementById,
                           WrappedElementById, Backoff, ConfirmDialog,
                           $timeout) {

  // keep in sync with appengine_config.py
  var MIMIC_PROJECT_ID_QUERY_PARAM = '_mimic_project';

  $scope.output_window = null;

  // TODO: remove; don't maintain DOM references
  $scope.requested_popout = false;

  // TODO: remove once file contents are returned in JSON response
  $scope.no_json_transform = function(data) { return data; };

  $scope.logs = [];

  $scope.clear_logs = function() {
    $scope.logs = [];
  }

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
    var url = '/_ah/mimic/' + control_path + qs;
    if ($scope.config.PLAYGROUND_USER_CONTENT_HOST) {
      url = '//' + $scope.config.PLAYGROUND_USER_CONTENT_HOST + url;
    }
    return url;
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
    $scope.files = {};
    return $http.get(url)
    .success(function(data, status, headers, config) {
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
  };

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
  };

  $scope.$on('$routeUpdate', function(evt) {
    var file = $scope.files[$location.hash()];
    if (file) {
      $scope.select_file(file);
    } else {
      $scope._select_a_file();
    }
  });

  $scope._select_a_file = function() {
    var path = $location.hash() || $scope.project.open_files[0];
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

  $scope.touch_project = function(project_key) {
    // Stops calling touch_project if on different page.
    if ($routeParams.project_id != project_key) {
      return;
    }
    // Calls touch project repeatedly to prevent expiration.
    return $http.post('/playground/p/' + 
      encodeURI(project_key) + '/touch')
    .success(function(data, status, headers, config) {
      for (var i in $scope.projects) {
        if ($scope.projects[i].key == project_key) {
          $scope.project = $scope.projects[i] = data;
          break;
        }
      }
      if ($scope.project.expiration_seconds) {
        $timeout(function() {
          $scope.touch_project($scope.project.key);
        }, $scope.project.expiration_seconds*1000/2);
      }
    });
  };

  DoSerial
  .then(function() {
    if (!setcurrentproject()) {
      // project_id is not in $scope.projects
      return $scope.retrieveproject()
      .then(setcurrentproject);
    }
  })
  .then($scope._list_files)
  .then($scope._select_a_file)
  .then($scope.set_loaded)
  .then(function() {
    $scope.touch_project($scope.project.key);
  });

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
  $window.addEventListener('message', function(evt) {
    if (!evt || !evt.data) {
      return;
    }
    var msg;
    if (msg = evt.data['socket.onopen']) {
      // give Channel API opportunity to become fully setup
      // https://code.google.com/p/googleappengine/issues/detail?id=7571
      $timeout($scope.run, 1000);
    } else if (msg = evt.data['socket.onmessage']) {
      var log_entry = JSON.parse(msg.data);
      // $sce helps defend against hostile input
      $scope.logs.push(log_entry);
    } else if (msg = evt.data['navigate_to']) {
      $scope.set_path(msg.path);
    }
    $scope.$apply();
  });

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
    var okButtonText = 'DELETE FILE';
    var okButtonClass = 'btn btn-danger';
    var callback = function() {
      delete_file(file);
    }

    ConfirmDialog(title, msg, okButtonText, okButtonClass, callback);
  }

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
    $scope.requested_popout = true;
    $scope.output_window = undefined;
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
      $scope.clear_logs();
    })
    .then(function() {
      // TODO: try to avoid DOM access
      if ($scope.output_window && $scope.output_window.closed) {
        $scope.requested_popout = false;
      }
      if ($scope.requested_popout) {
        // TODO: create open window service (so we can test)
        // TODO: read https://github.com/vojtajina/ng-directive-testing
        $scope.output_window = window.open($scope.project.run_url,
                                           $scope.project.key);
      } else {
        $scope.iframe_run_url = $sce.trustAsResourceUrl('about:blank');
        $timeout(function() {
          $scope.output_ready = false;
          var trusted_url = $sce.trustAsResourceUrl($scope.project.run_url);
          $scope.iframe_run_url = trusted_url;
        });
      }
    });
  };

  $scope.output_loaded = function() {
    $scope.output_ready = true;
  };

  $scope.reset_project = function() {
    var project_id = $scope.namespace();
    return $http.post('/playground/p/' + encodeURI(project_id) + '/reset')
    .success(function(data, status, headers, config) {
      for (var i in $scope.projects) {
        if ($scope.projects[i].key == data.key) {
          $scope.projects[i] = data;
          break;
        }
      }
      DoSerial
      .then($scope._list_files)
      .then(function() {
        $scope._select_a_file();
      });
    });
  };

  $scope.prompt_reset_project = function() {
    var title = 'Confirm project reset';
    var msg = 'Are you sure you want to reset project "' +
              $scope.project.name +
              '"?';
    var okButtonText = 'RESET PROJECT';
    var okButtonClass = 'btn btn-danger';
    var callback = function() {
      $scope.reset_project();
    }

    ConfirmDialog(title, msg, okButtonText, okButtonClass, callback);
  };

  $scope.download_project = function() {
    var project_id = $scope.namespace();
    $window.location = '/playground/p/' + encodeURI(project_id) + '/download';
  }

  $scope.prompt_download_project = function() {
    var title = 'Confirm project download';
    var msg = 'Are you sure you want to download project "' +
              $scope.project.name +
              '"?';
    var okButtonText = 'DOWNLOAD PROJECT';
    var okButtonClass = 'btn btn-primary';
    var callback = function() {
      $scope.download_project();
    }

    ConfirmDialog(title, msg, okButtonText, okButtonClass, callback);
  };

  $scope.$watch('selected_path', function(newpath, oldpath) {
    if (!newpath) {
      return;
    }
    if ($scope.current_file != $scope.files[newpath]) {
      $scope.select_file($scope.files[newpath]);
    }
  });

  $scope.$watch('current_file', function(newfile, oldfile) {
    if (!newfile) {
      return;
    }
    if ($scope.selected_path != newfile.path) {
      $scope.selected_path = newfile.path;
    }
  });

  $scope.$watch('project.control_url', function(value) {
    if (value) {
      $scope.control_url = $sce.trustAsResourceUrl(value);
    }
  });

}
