'use strict';

/* Directives */

angular.module('playgroundApp.directives', [])

// TODO: DETERMINE how must of this we should test
.directive('resizer', function(WrappedElementById) {

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
      elem = WrappedElementById(attr.resizer);
      initialheight = elem.prop('offsetHeight');
      dragDiv.removeClass('hidden');
      dragDiv.bind('mousemove', movefunc);
      dragDiv.bind('mouseup', upfunc);
    });
  };

})
