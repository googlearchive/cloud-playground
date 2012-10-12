angular.module('blissful', ['ngResource'])

.config(function($httpProvider) {
  $httpProvider.responseInterceptors.push('blissHttpInterceptor');
})

.factory('blissHttpInterceptor', function($q) {
  return function(promise) {
    return promise.then(function(response) {
      return response;
    }, function(reason) {
      if (reason instanceof Error) {
        alert(reason);
      } else if (reason.headers('X-Bliss-Error')) {
        alert('Error:\n' + reason.data);
      }
      return $q.reject(reason);
    });
  };
});

function ProjectController($scope, $http, $resource, $filter) {

  var Files = $resource('listfiles');

  var _dirty = false;
  var _save_timeout;

  // called from setTimeout after editor is marked dirty
  function save() {
    if (!_dirty) {
      return;
    }

    // TODO: fix me
    _dirty = false;

    set_status('Saving...');

    $scope.putfile($scope.currentFilename(), _editor.getValue());
  }

  function markDirty() {
    _dirty = true;

    if (_save_timeout) {
      return;
    }
    _save_timeout = setTimeout(function() {
      _save_timeout = null;
      save();
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
    $http({method: 'POST',
           url: 'deletepath/' + encodeURI(filename)})
    .success(function(data, status, headers, config) {
      $scope.files.splice($scope.currentIndex, 1);
      $scope.select(0);
    });
  };

  $scope.movefile = function(path, newpath) {
    $http({method: 'POST',
         url: 'movefile/' + encodeURI(path),
         data: {newpath: newpath}})
    .success(function(data, status, headers, config) {
      $scope.files[$scope.currentIndex].name = newpath;
      $scope.orderFilesAndSelectByPath(newpath);
    });
  };

  $scope.putfile = function(filename, data) {
    $http({method: 'PUT',
           url: 'putfile/' + encodeURI(filename),
           data: data})
    .success(function(data, status, headers, config) {
      set_status(); // Saved
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
    $scope.currentIndex = i;

    url = '//' + $scope.config.BLISS_USER_CONTENT_HOST +
          document.location.pathname + 'getfile/' +
          encodeURI($scope.currentFilename());
    $http({method: 'GET',
           url: url,
           transformResponse: noTransform})
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
    $http({method: 'GET',
           url: 'getconfig'})
    .success(function(data, status, headers, config) {
       $scope.config = data;
       listfiles();
    });
  };

  getconfig();

}
