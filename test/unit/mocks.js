
angular.module('mocks.dialog', [])

.provider('$dialog', function() {
  return {
    $get: function() {
      var dialogMock = {};
      var dialog_expectation;
      var expected_title, expected_msg, expected_btns;
      var userInput;

      // TODO: Refactor the way to set expectations.
      dialogMock.dialogShouldBeCalledWith = function(arg) {
        dialog_expectation = arg;
      };

      dialogMock.messageBoxShouldBeCalledWith = function(title, msg, btns) {
        expected_title = title;
        expected_msg = msg;
        expected_btns = btns;
      };

      dialogMock.willCloseWith = function(mockInput) {
        userInput = mockInput;
      };

      dialogMock.messageBox = function(title, msg, btns) {
        if (expected_title && expected_title != title) {
          throw Error('Expected title:' + expected_title +
                      ', Actual:' + title);
        }
        if (expected_msg && expected_msg != msg) {
          throw Error('Expected msg:' + expected_msg + ', Actual:' + title);
        }
        if (expected_btns) {
          expect(btns).toEqual(expected_btns);
        }
        return createMockDialog(userInput);
      };

      dialogMock.dialog = function(arg) {
        // TODO: Check options other than controller and templateUrl
        if (dialog_expectation &&
            (dialog_expectation.controller != arg.controller ||
             dialog_expectation.templateUrl != arg.templateUrl)) {
          throw Error('Expected:' + prettyPrint(dialog_expectation) +
                      ', Actual:' + prettyPrint(arg));
        }
        return createMockDialog(userInput);
      };
      return dialogMock;
    }
  };
});

function createMockDialog(userInput) {
  return {'open': function() {
    return {'then': function(callBack) {
      callBack(userInput);
    }};
  }};
}

function prettyPrint(data) {
  return (angular.isString(data) || angular.isFunction(data) || data instanceof RegExp)
    ? data
    : angular.toJson(data);
}
