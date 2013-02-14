
angular.module('mocks.dialog', [])

.provider('$dialog', function() {
  return {
    $get: function() {
      var dialogMock = {};
      var expectation;
      var userInput;

      dialogMock.shouldBeCalledWith = function(arg) {
        expectation = arg;
      };

      dialogMock.willCloseWith = function(mockInput) {
        userInput = mockInput;
      };

      dialogMock.dialog = function(arg) {
        // TODO: Check options other than controller and templateUrl
        if (expectation &&
            (expectation.controller != arg.controller ||
             expectation.templateUrl != arg.templateUrl)) {
          throw Error('Expected:' + prettyPrint(expectation) + 'Actual:' +
                      prettyPrint(arg));
        }
        return {'open': function() {
          return {'then': function(callBack) {
            callBack(userInput);
          }};
        }};
      };
      return dialogMock;
    }
  };
});

function prettyPrint(data) {
  return (angular.isString(data) || angular.isFunction(data) || data instanceof RegExp)
    ? data
    : angular.toJson(data);
}
