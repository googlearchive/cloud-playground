var blissfulModule = angular.module('blissful', []);

function ProjectController($scope, $http) {

  var listfiles = function() {
    $http({method: 'GET', url: 'listfiles/'}).
      success(function(data, status, headers, config) {
        var files = data;
        populateFilenames(files);
        if (files.length) {
          // select a file
          selectFile('file-0');
        }
      }).
      error(function() {
        alert('FIXME: listfiles');
      });
  };

  var whoami = function() {
    $http({method: 'GET', url: 'whoami'}).
      success(function(data) {
        _whoami = data;
        initLeftNavClickHandler();
        initFileContextMenuClearHandler();
        listfiles();
      }).
      error(function() {
        alert('FIXME: whoami');
      });
  };

  whoami();
}
