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
    })
  }
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

// TODO: DETERMINE how must of this we should test
.directive('pgResizer', function(WrappedElementById) {

  var downx, downy, isdown, initialheight, elem;
  var dragDiv = WrappedElementById('drag-div');

  function movefunc(evt) {
    if (!isdown) {
      return;
    }
    var newheight = initialheight + (evt.pageY - downy);
    elem.css('height', newheight + 'px');
  };

  function upfunc(evt) {
    isdown = false;
    dragDiv.addClass('hidden');
    dragDiv.unbind('mousemove', movefunc);
    dragDiv.unbind('mouseup', upfunc);
  };

  return function(scope, element, attr) {
    element.css({
      cursor: 'move',
      borderTop: '4px solid #fff',
      borderBottom: '4px solid #fff',
      backgroundColor: '#eee',
      padding: '2px',
    });
    element.bind('mousedown', function(evt) {
      evt.preventDefault();
      isdown = true;
      downx = evt.pageX;
      downy = evt.pageY;
      elem = WrappedElementById(attr.pgResizer);
      initialheight = elem.prop('offsetHeight');
      dragDiv.removeClass('hidden');
      dragDiv.bind('mousemove', movefunc);
      dragDiv.bind('mouseup', upfunc);
    });
  };

});
