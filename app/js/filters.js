'use strict';

/* Filters */

angular.module('playgroundApp.filters', [])

.filter('pathonly', function() {
  var re = new RegExp('.*/');
  return function(text) {
    return text.replace(re, '');
  }
});
