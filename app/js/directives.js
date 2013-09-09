'use strict';

/* Directives */

angular.module('playgroundApp.directives', [])

// TODO: test
.directive('pgMovable', function() {
  return function(scope, elm, attrs, controller) {
    scope.$watch(attrs.pgMovable, function(value) {
      if (value) {
        elm.css('left', value[0] + 'px');
        elm.css('top', value[1] + 'px');
      }
    });
  };
})

// TODO: test
.directive('pgVisible', function() {
  return function(scope, iElement, iAttrs, controller) {
    scope.$watch(iAttrs.pgVisible, function(value) {
      iElement.css({
        visibility: value ? 'visible' : 'hidden',
      });
    });
  };
})

// TODO: test
.directive('pgLoad', function() {
  return function(scope, iElement, iAttrs, controller) {
    scope.$watch(iAttrs.pgVisible, function(value) {
      iElement.bind('load', function(evt) {
        scope.$apply(iAttrs.pgLoad);
      });
    });
  };
})

// TODO: DETERMINE how must of this we should test
.directive('pgResizer', function(WrappedElementById) {

  var dragDiv = WrappedElementById('drag-div');

  function setElemHeight(elem, height) {
    elem.css('height', height + 'px');
  };

  function getHeight(key) {
    try {
      var height = localStorage.getItem('pgResizer-height-' + key);
      return Math.max(parseInt(height), 0);
    } catch (e) {
      return 0;
    }
  }

  function setHeight(key, height) {
    localStorage.setItem('pgResizer-height-' + key, height);
  }

  return function(scope, element, attr) {
    var downY, isDown;
    var containerElem = WrappedElementById(attr.pgResizer);

    if (scope.iframed) {
      return;
    }

    element.addClass('pg-resizer');
    if (getHeight(attr.pgResizer)) {
      setElemHeight(containerElem, getHeight(attr.pgResizer));
    }
    element.bind('mousedown', function(evt) {
      evt.preventDefault();
      isDown = true;
      downY = evt.pageY;
      dragDiv.removeClass('hidden');

      if (!getHeight(attr.pgResizer)) {
        setHeight(attr.pgResizer, containerElem.prop('offsetHeight'));
      }

      var movefunc = function(evt) {
        setHeight(attr.pgResizer,
                  getHeight(attr.pgResizer) + (evt.pageY - downY));
        downY = evt.pageY;
        setElemHeight(containerElem, getHeight(attr.pgResizer));
      };

      var upfunc = function(evt) {
        isDown = false;
        dragDiv.addClass('hidden');
        dragDiv.unbind('mousemove', movefunc);
        dragDiv.unbind('mouseup', upfunc);
      };

      dragDiv.bind('mousemove', movefunc);
      dragDiv.bind('mouseup', upfunc);
    });
  };

});
