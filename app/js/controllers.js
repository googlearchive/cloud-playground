'use strict';

/* Controllers */

// TODO: test
function AlertController($scope, Alert) {

  $scope.alerts = Alert.alerts;

  $scope.closeAlert = function(idx) {
    Alert.remove_alert(idx);
  };

  $scope.$on('$routeChangeStart', function() {
    Alert.clear();
  });
}

function HeaderController($scope, $location, $routeParams) {
  $scope.read_only = !!($location.search()['read_only']);

  $scope.alreadyhome = function() {
    return $location.path() == '/playground/';
  };

  // TODO: test
  $scope.$on('$routeChangeSuccess', function(evt, current, previous) {
    if (!previous) {
      if ($routeParams.template_url) {
        track('first-page-load', $routeParams.template_url);
      } else if ($scope.alreadyhome()) {
        track('first-page-load', 'main-page');
      } else if ($location.path().match(/^\/playground\/p\//)) {
        track('first-page-load', 'project-page');
      } else {
        track('first-page-load', $location.path());
      }
     }
   });
}

// TODO: test
function RenameProjectController($scope, $log, dialog, project_name) {

  $scope.project_name = project_name;

  $scope.close = function(project_name) {
    dialog.close(project_name);
  };

}

function PageController($scope, $http, DoSerial, $routeParams, $window,
                        $dialog, $location, $log, WindowService, $rootScope,
                        ConfirmDialog, $q, ConfigService, ProjectsFactory) {

  $scope.read_only = !!($location.search()['read_only']);
  $scope.show_sidebar = (!!($location.search()['show_sidebar']) &&
                         $window.iframed);
  $scope.show_project_title = (!!($location.search()['show_project_title']) &&
                               $window.iframed);

  // TODO: test
  $scope.$on('$routeChangeError', function(evt, current, previous, rejection) {
    $log.log('PageController routeChangeError:', rejection);
    if (rejection.status == 401) {
      $rootScope.set_load_state('ACCESS_DENIED');
    } else {
      $rootScope.set_load_state(rejection);
    }
  });

  // TODO: test
  $scope.$on('$routeChangeSuccess', function(evt, current, previous) {
    $scope.iframed = $window.iframed;

    ProjectsFactory
    .then(function(projects_service) {
      $scope.projects_service = projects_service;
      $scope.projects = projects_service.projects;
    });
    ConfigService
    .then(function(config_service) {
      $scope.config = config_service.config;
    })
  });

  $scope.show_project_in_list = function(project) {
    return $scope.config.is_admin || !project.hide_template;
  };

  $scope.namespace = function() {
    return $routeParams.project_id ||
           ($scope.config && $scope.config.playground_namespace);
  };

  $scope.to_main_page = function(label) {
    track('to-main-page', label);
    $location.replace();
    $location.path('/playground/').hash('');
  }

  $scope.signin = function(label) {
    track('sign-in', label);
    WindowService.go('/playground/login');
  }

  $scope.signout = function(label) {
    track('sign-out', label);
    WindowService.go('/playground/logout');
  }

  $scope.open_datastore_admin = function(label) {
    track('open-datastore-admin', label);
    WindowService.open('/playground/datastore/' + $scope.namespace(), '_blank');
  };

  $scope.open_memcache_admin = function(label) {
    track('open-memcache-admin', label);
    WindowService.open('/playground/memcache/' + $scope.namespace(), '_blank');
  };

  $scope.open_git_project = function(label) {
    track('open-git-project', label);
    WindowService.open($scope.config.git_playground_url, '_blank');
  };

  $scope.reload = function(label) {
    track('reload', label);
    WindowService.reload();
  };

  $scope.popout_ide = function(label) {
    track('popout-ide', label);
    WindowService.open($location.absUrl(), '_blank');
  }

  $scope.big_red_button = function(label) {
    track('big-red-button', label);
    DoSerial
    .then(function() {
      return $http.post('/playground/nuke')
      .success(function(data, status, headers, config) {
        WindowService.reload();
      });
    });
  };

  // TODO: test
  $scope.set_oauth2_admin = function(credential, label) {
    track('set-oauth2-admin', credential.key, label);
    $http.post('/playground/oauth2_admin', credential);
  };

  // TODO: test
  $scope.prompt_oauth2_admin = function(key, url, label) {
    track('prompt-oauth2-admin', key, label);
    $http.post('/playground/oauth2_admin', {key: key, url: url})
    .success(function(data, status, headers, config) {
      $dialog.dialog({
          controller: 'OAuth2AdminController',
          templateUrl: '/playground/oauth2_admin.html',
          resolve: {
              key: data.key,
              url: data.url,
              client_id: data.client_id,
              client_secret: data.client_secret,
          },
      })
      .open().then(function(credential) {
        if (!credential) {
          return;
        }
        $scope.set_oauth2_admin(credential, label);
      });
    });
  };

  $scope.select_project = function(project, label) {
    $location.replace();
    track('select-project', label, project.template_url);
    $location.path('/playground/p/' + encodeURI(project.key));

    // Remove all params except the display flags.
    var params_to_preserve = ['read_only', 'show_sidebar', 'show_project_title'];
    var new_params = {};
    for (var pname in params_to_preserve) {
      var pval = $location.search()[pname];
      if (pval) {
        new_params[pname] = pval;
      }
    }
    $location.search(new_params);
  };

  $scope.delete_project = function(project, label) {
    $location.replace();
    track('delete-project', label, project.template_url);
    $scope.projects_service.remove(project);
    $scope.project = undefined;
    $location.path('/playground/');
  };

  $scope.prompt_delete_project = function(project, label) {
    if (project.owner.indexOf('@') >= 0 && $scope.config.is_admin) {
      $scope.delete_project(project, label);
      return;
    }
    track('prompt-delete-project', label);
    var title = 'Confirm project deletion';
    var msg = 'Are you sure you want to delete project "' + project.name +
              '"?';
    var okButtonText = 'DELETE PROJECT';
    var okButtonClass = 'btn btn-danger';
    var callback = function() {
      $scope.delete_project(project, label);
    }

    ConfirmDialog(title, msg, okButtonText, okButtonClass, callback);
  };

  $rootScope.set_load_state = function(load_state) {
    if (typeof load_state != 'boolean') {
      track('set-load-state', load_state);
    }
    $scope.load_state = load_state;
  }

  $rootScope.set_load_state(false);
}

function MainController($scope, $http, $window, $location, $log, $routeParams,
                        $q, Alert, DoSerial, $rootScope) {

  // TODO: test
  $scope.$on('$routeChangeError', function(evt, current, previous, rejection) {
    $log.log('MainController routeChangeError:', rejection);
    $rootScope.set_load_state(rejection);
  });

  // TODO: test
  $scope.$on('$routeChangeSuccess', function(evt, current, previous) {
    DoSerial
    .then(function() {
      var template_url = $routeParams.template_url;
      if (template_url) {
        var expiration_seconds = parseInt($routeParams.expiration_seconds);
        return $scope.new_project_from_template_url(template_url, expiration_seconds, 'auto-from-template-url')
        .then(function(project) {
          $scope.select_project(project, 'auto-from-template-url');
        })
        .catch(function(rejection) {
          $rootScope.set_load_state(rejection);
        });
      } else {
        $rootScope.set_load_state(true);
      }
    });
  });

  // TODO: test
  $scope.new_project_from_template_url = function(repo_url, expiration_seconds, label) {
    track('new-project-from-template-url', label, repo_url);
    return $http.post('/playground/new_project_from_template_url', {
      repo_url: repo_url,
    })
    .then(function(resolved) {
      var project = resolved.data;
      $scope.projects.push(project);
      return project;
    })
    .catch(function(rejection) {
      if (rejection.status == 408) {
        return $q.reject('TEMPLATE_NOT_YET_AVAILABLE');
      }
      return $q.reject(rejection);
    });
  };

  // TODO: test
  $scope.create_template_project_by_url = function(repo_url, label) {
    track('create-template-project-by-url', label, repo_url);
    var deferred = $q.defer();
    DoSerial
    .then(function() {
      var data = {
        'name': '(Creating template project...)',
        'description': '(Please wait...)',
        'in_progress_task_name': 'foo',
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

  $scope.new_project = function(template_project, expiration_seconds, label) {
    track('new-project', label, template_project.template_url);
    var deferred = $q.defer();
    var data = {
      'name': '(Creating project...)',
      'description': '(Please wait and then refresh this page.)',
      'in_progress_task_name': 'foo',
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
                           $timeout, $rootScope, $q) {

  // keep in sync with appengine_config.py
  var MIMIC_PROJECT_ID_QUERY_PARAM = '_mimic_project';

  $scope.output_window = null;

  // TODO: remove; don't maintain DOM references
  $scope.requested_popout = false;

  // variable lifecycle: undefined -> false -> true -> false -> true -> ...
  $scope.output_ready = undefined;

  // ensures exactly one automatic run after channel API socket opens
  $scope.app_run_count = 0;

  // TODO: remove once file contents are returned in JSON response
  $scope.no_json_transform = function(data) { return data; };

  $scope.logs = [];

  // TODO: test
  $scope.$on('$routeChangeError', function(evt, current, previous, rejection) {
    $rootScope.set_load_state(rejection);
    $log.log('ProjectController routeChangeError:', rejection);
  });

  // TODO: test
  $scope.$on('$routeChangeSuccess', function(evt, current, previous) {
    DoSerial
    .then(function() {
      var deferred = $q.defer();
      deferred.resolve();
      deferred.promise
      .then(function() {
        if (!setcurrentproject()) {
          // project_id is not in $scope.projects
          return $scope.retrieveproject()
          .catch(function(e) {
            $rootScope.set_load_state(e);
            return $q.reject(e);
          })
          .then(setcurrentproject);
        }
      })
      .then(function() {
        $scope.control_url = $sce.trustAsResourceUrl($scope.project.control_url);
      })
      .then($scope._list_files)
      .then(function() {
        $scope.visible_files = $scope.calculate_visible_files(
          $scope.project, $scope.files);
        $scope._select_a_file('auto-route-change-success');
      })
      .then(function() {
        $rootScope.set_load_state(true);
      })
      .then(function() {
        $scope.update_project($scope.project.key);
      });
      return deferred.promise;
    })
  });

  $scope.retrieveproject = function() {
    $scope.status = 'Retrieving project ' + project_id;
    var project_id = $scope.namespace();
    return $http.get('/playground/p/' + encodeURI(project_id) + '/retrieve')
    .success(function(data, status, headers, config) {
      $scope.projects.push(data);
    })
    .catch(function(rejection) {
      if (rejection.headers('X-Cloud-Playground-Error')) {
        if (rejection.status == 401) {
          return $q.reject('PROJECT_ACCESS_DENIED');
        } else if (rejection.status == 404) {
          return $q.reject('PROJECT_NOT_FOUND');
        }
      }
      return $q.reject(rejection);
    });
  };

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
      $timeout(function() {
        // $timeout here ensures the codemirror finishes initialization.
        file.contents = data;
        file.dirty = false;
        success_cb();
      }, 0);
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
      angular.forEach(data, function(file, i) {
        $scope.files[file.path] = file;
      });
    });
  };

  // TODO: test
  function _save(path, label) {
    track('save', label, path)
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
          return _save(dirtypath, 'save-dirty-files');
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

  $scope.select_file = function(file, label) {
    if (file == $scope.current_file) {
      if ($location.hash() != file.path) {
        // user was on a valid file, then changed hash to invalid path
        $location.replace();
        $location.hash(file.path);
      }
      return;
    }
    track('select-file', label, file.path);
    if ($scope.is_image_mime_type(file.mime_type)) {
      $scope.current_file = file;
      $location.replace();
      $location.hash(file.path);
      return;
    }
    $scope._get(file, function() {
      $location.replace();
      $scope.current_file = file;
      $location.hash(file.path);
    });
  };

  $scope.set_path = function(path) {
    var file = $scope.files[path];
    if (file) {
      $scope.select_file(file, 'set-path');
    } else {
      $scope._select_a_file('set-path');
    }
  };

  $scope.$on('$routeUpdate', function(evt) {
    var file = $scope.files[$location.hash()];
    if (file == $scope.current_file) {
      return;
    }
    if (file) {
      $scope.select_file(file, '$routeUpdate');
    } else {
      $scope._select_a_file('$routeUpdate');
    }
  });

  $scope._select_a_file = function(label) {
    var path = $location.hash() || $scope.project.show_files[0];
    var file = $scope.visible_files[path];
    if (file) {
      $scope.select_file(file, label);
      return;
    }

    // select first visible file
    for (var path in $scope.visible_files) {
      $scope.select_file($scope.visible_files[path], 'auto-first-file');
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

  $scope.update_project = function(project_key, data) {
    // Stop calling update_project if on different page.
    if ($routeParams.project_id != project_key) {
      return;
    }
    // Calls update_project repeatedly to prevent expiration.
    return $http.post('/playground/p/' +
      encodeURI(project_key) + '/update', data)
    .success(function(data, status, headers, config) {
      for (var i in $scope.projects) {
        if ($scope.projects[i].key == project_key) {
          $scope.project = $scope.projects[i] = data;
          break;
        }
      }
      if ($scope.project.expiration_seconds) {
        $timeout(function() {
          $scope.update_project($scope.project.key);
        }, $scope.project.expiration_seconds*1000/2);
      }
    });
  };

  $scope.mark_as_open_file = function(path) {
    if ($scope.project.show_files.length == 0) {
      // project doesn't use a show_files list
      return;
    }
    var existing_show_file = false;
    angular.forEach($scope.project.show_files, function(show_file) {
      if (path == show_file) {
        existing_show_file = true;
      }
    });
    if (existing_show_file) {
      return;
    }
    $scope.project.show_files.push(path);
    $scope.update_project($scope.project.key,
                          {show_files: $scope.project.show_files})
  }

  // TODO: test
  $scope.new_file = function(path, label) {
    track('new-file', label, path);
    var file = $scope.files[path];
    $scope.mark_as_open_file(path);
    if (!file) {
      // Create a file on the server side and use the result.
      $http.put($scope.url_of('file', {path: path}), '', {
        headers: {'Content-Type': 'text/plain; charset=utf-8'}
      })
      .success(function(data, status, header, config) {
        $scope.files[path] = data;
        $scope.select_file(data, 'new-file');
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
      $scope.select_file(file, 'new-file-existing');
    }
  };

  // TODO: test
  $scope.prompt_new_file = function(label) {
    track('prompt-new-file', label);
    $dialog.dialog({
        controller: 'NewFileController',
        templateUrl: '/playground/new_file_modal.html',
        resolve: {path: ''},
    })
    .open().then(function(path) {
      if (path) {
        // remove leading and trailing slash(es)
        path = path.replace(/^\/*(.*?)\/*$/, '$1');
        $scope.new_file(path, label);
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
      $timeout(function() {
        // socket.onopen may be called more than once and user can manually run
        if ($scope.app_run_count == 0) {
          // $scope.run('auto-delayed-onload');
        }
      }, 2000);
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
  $scope.project_context_menu = function(evt, label) {
    track('project-context-menu', label);
    evt.stopPropagation();
    hide_context_menus();
    $scope.showprojectcontextmenu = true;
    $scope.project_context_menu_pos = [evt.pageX, evt.pageY];
  };

  // TODO: test
  function project_rename(project, name, label) {
    track('project-rename', label, project.template_url);
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
  $scope.prompt_project_rename = function(project, label) {
    track('prompt-project-rename', label);
    $dialog.dialog({
        controller: 'RenameProjectController',
        templateUrl: '/playground/rename_project_modal.html',
        resolve: {project_name: project.name},
    })
    .open().then(function(name) {
      if (name) {
        project_rename(project, name, label);
      }
    });
  };

  // TODO: test
  $scope.file_context_menu = function(evt, file, label) {
    track('file-context-menu', label, file.path);
    evt.stopPropagation();
    hide_context_menus();
    $scope.select_file(file, 'file-context-menu');
    $scope.showfilecontextmenu = true;
    $scope.file_context_menu_pos = [evt.pageX, evt.pageY];
  };

  // TODO: test
  function delete_file(file, label) {
    track('delete-file', label, file.path);
    DoSerial
    .then(function() {
      var url = $scope.url_of('delete', {path: file.path});
      return $http.post(url)
      .success(function(data, status, headers, config) {
        delete $scope.files[file.path];
        $scope._select_a_file('delete-file');
      });
    });
  };

  // TODO: test
  $scope.prompt_delete_file = function(file, label) {
    track('prompt-delete-file', label, file.path);
    var title = 'Confirm file deletion';
    var msg = 'Are you sure you want to delete file "' +
              $scope.current_file.path + '"?';
    var okButtonText = 'DELETE FILE';
    var okButtonClass = 'btn btn-danger';
    var callback = function() {
      delete_file(file, label);
    }

    ConfirmDialog(title, msg, okButtonText, okButtonClass, callback);
  }

  // TODO: test
  function file_rename(file, path, label) {
    track('file-rename', label, path);
    if (!path || path == file.path) {
      return;
    }
    $scope.mark_as_open_file(path);
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
  $scope.prompt_file_rename = function(file, label) {
    track('prompt-file-rename', label, file.path);
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
      file_rename(file, path, label);
    });
  };

  // TODO: test
  $scope.popout = function(label) {
    track('popout', label);
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
  $scope.run = function(label) {
    track('run', label);
    $scope.app_run_count++;
    return DoSerial
    // TODO: _save_dirty_files must succeed before running
    .then(_save_dirty_files)
    .then($scope.clear_logs)
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
    if (typeof $scope.output_ready === 'undefined') {
      return;
    }
    $scope.output_ready = true;
  };

  $scope.reset_project = function(label) {
    track('reset-project', label);
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
        $scope._select_a_file('reset-project');
      });
    });
  };

  $scope.prompt_reset_project = function(label) {
    track('prompt-reset-project', label);
    var title = 'Confirm project reset';
    var msg = 'Are you sure you want to reset project "' +
              $scope.project.name +
              '"?';
    var okButtonText = 'RESET PROJECT';
    var okButtonClass = 'btn btn-danger';
    var callback = function() {
      $scope.reset_project(label);
    }

    ConfirmDialog(title, msg, okButtonText, okButtonClass, callback);
  };

  $scope.download_project = function(filename, label) {
    track('download-project', label);
    var project_id = $scope.namespace();
    $window.location = $scope.url_of('zip', {filename: filename});
  };

  $scope.handle_download_button = function(project) {
    var filename = project.download_filename;
    if (!filename) {
      filename = project.name;
      filename = filename.replace(/[^a-zA-Z0-9-]/g, '_');
      filename = filename + '.zip';
    }
    $scope.download_project(filename, 'project-download-button');
  };

  $scope.prompt_download_project = function(label) {
    track('prompt-download-project', label);
    var title = 'Confirm project download';
    var msg = 'Are you sure you want to download project "' +
              $scope.project.name +
              '"?';
    var okButtonText = 'DOWNLOAD PROJECT';
    var okButtonClass = 'btn btn-primary';
    var callback = function() {
      var filename = $scope.project.name + ' - ' + $scope.project.key + '.zip';
      $scope.download_project(filename, label);
    }

    ConfirmDialog(title, msg, okButtonText, okButtonClass, callback);
  };

  /**
   * Calculates visible files based on a project.
   *
   * @param {object} project The project whose visibility settings to use.
   * @param {object} files A mapping of filenames to file objects.
   * @return {object} A mapping of filenames to file objects for just those
   *     files considered visible for the project.
   */
  $scope.calculate_visible_files = function(project, files) {
    var show_files = project.show_files;
    if (show_files.length == 0) {
      // empty filter list implies no filtering
      // other than .playground file, if present
      for (var filename in files) {
        if (filename != '.playground' && files.hasOwnProperty(filename)) {
          show_files.push(filename);
        }
      }
    }

    var show_files_map = {};
    angular.forEach(show_files, function(show_file) {
      show_files_map[show_file] = true;
    });

    var read_only_files = project.read_only_files;
    var read_only_files_map = {};
    angular.forEach(read_only_files, function(read_only_file) {
      read_only_files_map[read_only_file] = true;
    });

    var visible_files = {};
    angular.forEach(files, function(file) {
      if (show_files_map[file.path]) {
        if (read_only_files_map[file.path]) {
          file.read_only = true;
        }

        visible_files[file.path] = file;
      }
    });

    return visible_files;
  };

  $scope.$watch('selected_path', function(newpath, oldpath) {
    if (!newpath || newpath == oldpath) {
      return;
    }
    $scope.set_path(newpath);
  });

  $scope.$watch('current_file', function(newfile, oldfile) {
    if (!newfile || newfile == oldfile) {
      return;
    }
    if ($scope.selected_path != newfile.path) {
      $scope.selected_path = newfile.path;
    }
  });

  $scope.$watch('files', function(newfiles, oldfiles) {
    if (newfiles == oldfiles) {
      return;
    }

    $scope.visible_files = $scope.calculate_visible_files(
        $scope.project, newfiles);
  }, true);

  $scope.$watch('visible_files', function(newfiles, oldfiles) {
    if (newfiles == oldfiles) {
      return;
    }
    $scope.visible_files_count = 0
    angular.forEach(newfiles, function(file) {
      $scope.visible_files_count++;
    });
  }, true);

  if ($scope.read_only) {
    $scope.run("read-only");
  }
}
