// TODO: replace with an angular-ui/bootstrap based mock
angular.module('mocks.dialog', [])

.provider('$dialog', function() {
  return {
    $get: function() {},
  };
})
