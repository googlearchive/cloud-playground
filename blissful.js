angular.module('blissful', ['ngResource'])

.config(function($httpProvider) {
  $httpProvider.responseInterceptors.push('blissHttpInterceptor');
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
        alert(err.status + ' <- ' + err.method + ' ' + err.url + '\n' +
              err.data);
        // TODO: address problems such as OPTIONS pre-flight request failures
        alert('FIXME: see console.log for details');
        console.log('err', err);
      }
      return $q.reject(err);
    });
  };
});

function MainController($scope, $http) {

  $scope.prompt_for_new_project = function(template_url, project_name,
                                           project_description) {
    box = lightbox('Creating project', 'Please wait.');
    $http.post('createproject', {
        template_url: template_url,
        project_name: project_name,
        project_description: project_description})
    .success(function(data, status, headers, config) {
      box();
      document.body.scrollTop = 0;
      window.location.reload();
    });
  };

  $scope.prompt_to_delete_project = function(project_id, project_name) {
    var answer = prompt("Are you sure you want to delete project " +
                        project_name + "?\nType 'yes' to confirm.", "no");
    if (!answer || answer.toLowerCase()[0] != 'y') {
      return;
    }
    $http.post('/bliss/p/' + encodeURI(project_id) + '/delete')
    .success(function(data, status, headers, config) {
      document.body.scrollTop = 0;
      window.location.reload();
    });
  };

}

function ProjectController($scope, $http, $resource, $filter) {

  var Files = $resource('listfiles');

  var _editor;
  var _dirty = false;
  var _save_timeout;
  var _output_window;
  var _popout = false;

  $scope.popout = function() {
    _popout = true;
    _output_window = undefined;
  }

  $scope.run = function(url, project_id) {
    $scope.save(function() {
      var container = document.getElementById('output-container');
      if (_output_window && _output_window.closed) {
        _popout = false;
      }
      if (_popout) {
        container.style.display = 'none';
        _output_window = window.open(url, project_id);
      } else {
        container.style.display = 'block';
        var where = document.getElementById('output-url');
        var iframe = document.getElementById('output-iframe');
        iframe.src = url;
        where.innerHTML = iframe.src;
      }
    });
  }

  // called from setTimeout after editor is marked dirty
  $scope.save = function(callback) {
    if (!_dirty) {
      if (callback) {
        callback.call();
      }
      return;
    }

    // TODO: fix me
    _dirty = false;

    set_status('Saving...');
    $scope.putfile($scope.currentFilename(), _editor.getValue(), function () {
      set_status(''); // saved
      if (callback) {
        callback.call();
      }
    });
  }

  function markDirty() {
    _dirty = true;

    if (_save_timeout) {
      return;
    }
    _save_timeout = setTimeout(function() {
      _save_timeout = null;
      $scope.save();
    }, 1000);
  }

  // editor onChange
  function editorOnChange(from, to, text, next) {
     markDirty();
  }

  $scope.prompt_file_delete = function() {
    var answer = prompt("Are you sure you want to delete " + $scope.currentFilename() + "?\nType 'yes' to confirm.", "no");
    if (!answer || answer.toLowerCase()[0] != 'y') {
      return;
    }
    $scope.deletepath($scope.currentFilename());
  }

  $scope.prompt_file_rename = function() {
    var new_filename = prompt(
        'New filename?\n(You may specify a full path such as: foo/bar.txt)',
        $scope.currentFilename());
    if (!new_filename) {
      return;
    }
    if (new_filename[0] == '/') {
      new_filename = new_filename.substr(1);
    }
    if (!new_filename || new_filename == $scope.currentFilename()) {
      return;
    }
    $scope.movefile($scope.currentFilename(), new_filename);
  }

  // setup file context menu clear handler
  window.addEventListener('click', function(evt) {
    document.getElementById('file-context-menu').style.display = 'None';
  }, false);

  $scope.file_context_menu = function(evt, i) {
    evt.stopPropagation();
    $scope.select(i);
    var menuDiv = document.getElementById('file-context-menu');
    menuDiv.style.display = 'block';
    menuDiv.style.left = evt.pageX + 'px';
    menuDiv.style.top = evt.pageY + 'px';
    var elem = document.getElementById('file-' + i);
    insertAfter(menuDiv, elem);
  };

  $scope.orderFilesAndSelectByPath = function(path) {
    $scope.files = $filter('orderBy')($scope.files, 'name');
    $scope.selectByPath(path);
  };

  $scope.insertPath = function(path) {
    if ($scope.selectByPath(path)) {
      return;
    }
    $scope.putfile(path, '');
    files = $scope.files;
    files.push({name: path});
    $scope.orderFilesAndSelectByPath(path);
  };

  $scope.prompt_for_new_file = function() {
    var filename = prompt('New filename?', '');
    if (!filename) {
      return;
    }
    if (filename[0] == '/') {
      filename = filename.substr(1)
    }

    $scope.insertPath(filename);
  };

  $scope.currentFilename = function() {
    if (!$scope.files) return '';
    return $scope.files[$scope.currentIndex].name;
  };

  $scope.deletepath = function(filename) {
    $http.post('deletepath/' + encodeURI(filename))
    .success(function(data, status, headers, config) {
      $scope.files.splice($scope.currentIndex, 1);
      $scope.select(0);
    });
  };

  $scope.movefile = function(path, newpath) {
    $http.post('movefile/' + encodeURI(path),{newpath: newpath})
    .success(function(data, status, headers, config) {
      $scope.files[$scope.currentIndex].name = newpath;
      $scope.orderFilesAndSelectByPath(newpath);
    });
  };

  $scope.putfile = function(filename, data, callback) {
    
    $http.put('putfile/' + encodeURI(filename), data, {
           headers: {'Content-Type': 'text/plain; charset=utf-8'}
    })
    .success(function(data, status, headers, config) {
      if (callback) {
        callback.call();
      }
    }).error(function(resp) {
      $scope.select($scope.currentIndex);
    });
  };

  $scope.selectByPath = function(path) {
    for (i in $scope.files) {
      if ($scope.files[i].name == path) {
        $scope.select(i);
        return true;
      }
    }
    return false;
  };

  var noTransform = function(data) { return data; };

  $scope.select = function(i) {
    $scope.save(function() {
      _select(i)
    });
  };

  var _select = function(i) {
    $scope.currentIndex = i;

    url = '//' + $scope.config.BLISS_USER_CONTENT_HOST +
          document.location.pathname + 'getfile/' +
          encodeURI($scope.currentFilename());
    $http.get(url, {transformResponse: noTransform})
    .success(function(data, status, headers, config) {
      // e.g. 'text/html; charset=UTF-8'
      var mime_type = headers('Content-Type');
      // strip '; charset=...'
      mime_type = mime_type.replace(/ ?;.*/, '');
      if (/^image\//.test(mime_type)) {
        source_image.setAttribute('src', config.url);
        source_container.setAttribute('class', 'image');
      } else {
        while(source_code.hasChildNodes()) {
          source_code.removeChild(source_code.childNodes[0]);
        }
        _editor = createEditor(mime_type);
        _editor.getScrollerElement().id = 'scroller-element';
        source_container.setAttribute('class', 'code');
        _editor.setValue(data);
        _editor.setOption('onChange', editorOnChange);
        _editor.focus();
      }
    });
  };

  var listfiles = function() {
    Files.query(function(files) {
      $scope.files = files;
      $scope.select(0);
    });
  };

  var getconfig = function() {
    $http.get('getconfig')
    .success(function(data, status, headers, config) {
       $scope.config = data;
       listfiles();
    });
  };

  getconfig();

}
