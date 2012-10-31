// DO THIS FIRST; REPLACE LATER
window.onerror = function(msg, url, line) {
  alert("JavaScript error on line " + line + " of " + url + "\n\n" + msg);
}

// Keep track of z-index to allow layering of multiple glass messages
var _glassMessageZIndex = 2147483647 - 100;


function lightbox(summary, details) {
  outer = document.createElement('div');
  _glassMessageZIndex += 2;
  // borrowed from GWT's hosted.html and adapted for bliss
  outer.innerHTML =
    '<div style="position:absolute;z-index:' + (_glassMessageZIndex + 1) +
    ';left:50px;top:50px;width:600px;color:#FFF;font-family:verdana;text-align:left;">' +
    '<div>' +
    '<button onclick="window.location.reload()" style="background-color:#fff;color:#000;">reload page</button>' +
    '<button onclick="outer=this.parentNode.parentNode.parentNode;outer.parentNode.removeChild(outer)" style="background-color:#fff;color:#000;">close</button>' +
    '</div>' +
    '<div style="font-size:30px;font-weight:bold;">' + summary + '</div>' +
    '<div style="font-size:15px;">' + details + '</div>' +
    '</div>' +
    '<div style="position:absolute;z-index:' + _glassMessageZIndex +
    ';left:0px;top:0px;right:0px;bottom:0px;filter:alpha(opacity=60);opacity:0.6;background-color:#000;"></div>'
  ;
  var container = document.getElementById('container') || document.body;
  container.appendChild(outer);
  document.body.scrollTop = 0;

  return function() {
    container.removeChild(outer);
  }
}

window.onerror = function(msg, url, line) {
  box = lightbox("JavaScript error on line " + line + " of " + url, msg);
}

// TODO: replace this handcrafted splitter
function resizer(divider_id, content_id) {
  divider = document.getElementById(divider_id);
  if (!divider) {
    return;
  }

  var downx, downy, isdown, initialheight, elem;
  var dragDiv = document.getElementById('drag-div');

  var movefunc = function(evt) {
    if (!isdown) {
      return;
    }
    var newheight = initialheight + (evt.pageY - downy);
    elem.style.height = newheight + 'px';
  };

  var downfunc = function(evt) {
    evt.preventDefault();
    isdown = true;
    downx = evt.pageX;
    downy = evt.pageY;
    elem = document.getElementById(content_id);
    initialheight = elem.offsetHeight;
    dragDiv.style.display = 'block';
    dragDiv.addEventListener('mousemove', movefunc);
    dragDiv.addEventListener('mouseup', upfunc);
  };

  var upfunc = function(evt) {
    isdown = false;
    dragDiv.style.display = 'none';
    dragDiv.removeEventListener('mousemove', movefunc);
    dragDiv.removeEventListener('mouseup', upfunc);
  };

  divider.addEventListener('mousedown', downfunc);
}
