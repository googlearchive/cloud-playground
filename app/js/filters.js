'use strict';

/* Filters */

angular.module('playgroundApp.filters', [])

.filter('file_filter', function() {
  return function(files, show_files) {
    if (show_files.length == 0) {
      // empty filter list implies no filtering
      return files;
    }
    var path_map = {};
    angular.forEach(show_files, function(open_file) {
      path_map[open_file] = true;
    });
    var new_files = [];
    angular.forEach(files, function(file) {
      if (path_map[file.path]) {
        new_files.push(file);
      }
    });
    return new_files;
  }
});
