// DO THIS FIRST; REPLACE LATER
window.onerror = function(msg, url, line) {
  alert("JavaScript error on line " + line + " of " + url + "\n\n" + msg);
}

// AngularJS XSRF Cookie, see http://docs.angularjs.org/api/ng.$http
var _XSRF_TOKEN_COOKIE = 'XSRF-TOKEN'

// AngularJS XSRF HTTP Header, see http://docs.angularjs.org/api/ng.$http
var _XSRF_TOKEN_HEADER = 'X-XSRF-TOKEN'

// Keep track of z-index to allow layering of multiple glass messages
var _glassMessageZIndex = 2147483647 - 100;

var source_container = document.getElementById('source-container');
var source_filename = document.getElementById('source-filename');
var source_code = document.getElementById('source-code');
var source_image = document.getElementById('source-image');


function set_status(status) {
  document.getElementById('status').innerHTML = status || '&nbsp;';
}

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

// XHR
function xhr(method, url, callback, data) {
  set_status('<img src="/bliss/spinner.png"/> <b>' + method + '</b> ' + url);
  setTimeout(function() { _xhr(method, url, callback, data); }, 0);
}

function safer(html) {
  return html.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function get_cookie(key) {
  cookies = document.cookie.split('; ')
  for (i=0; i<cookies.length; i++) {
    kv = cookies[i].split('=');
    if (kv[0] == key) {
      return kv[1];
    }
  }
  return null;
}

function _xhr(method, url, callback, data) {
  var xhr = new XMLHttpRequest();
  xhr.open(method, url, true);
  if (method != 'GET') {
    var xsrf = get_cookie(_XSRF_TOKEN_COOKIE);
    xhr.setRequestHeader(_XSRF_TOKEN_HEADER, xsrf);
  }
  if (method == 'POST') {
    xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded');
  }
  xhr.onreadystatechange = function() {
    if (xhr.readyState != 4) {
      return;
    }
    if (xhr.getResponseHeader('X-Bliss-Error')) {
      callback(xhr);
      alert('Error: ' + xhr.responseText);
    } else if (xhr.status != 200) {
      set_status('\nHTTP Status: ' + xhr.status + '\nURL: ' + url);
      // '.' does not match newlines, so use '[\s\S]' instead
      content = xhr.responseText.replace(/[\s\S]*<body>([\s\S]*)<\/body>[\s\S]*/, '$1');
      box = lightbox('HTTP Status: ' + xhr.status + '\nURL: ' + url, content);
    } else {
      set_status(); // XHR success
      callback(xhr);
    }
  }
  xhr.send(data);
}

// POST
function post(url, callback, data) {
  xhr('POST', url, function(xhr) {
    callback(xhr);
  }, data);
}

function insertAfter(newNode, existingNode) {
  var parentNode = existingNode.parentNode;
  if (existingNode.nextSibling) {
    return parentNode.insertBefore(newNode, existingNode.nextSibling);
  } else {
    return parentNode.appendChild(newNode);
  }
}

function prompt_for_new_project(template_url, project_name,
                                project_description) {
  var uri = '/bliss/createproject';
  var data = 'template_url=' + encodeURI(template_url) +
             '&project_name=' + encodeURI(project_name) +
             '&project_description=' + encodeURI(project_description);
  box = lightbox('Creating project', 'Please wait.');
  post(uri, function(xhr) {
    box();
    document.body.scrollTop = 0;
    window.location.reload();
  }, data);
}

function prompt_to_delete_project(project_id, project_name) {
  var answer = prompt("Are you sure you want to delete project " +
                      project_name + "?\nType 'yes' to confirm.", "no");
  if (!answer || answer.toLowerCase()[0] != 'y') {
    return;
  }
  var uri = '/bliss/p/' + encodeURI(project_id) + '/delete';
  post(uri, function(xhr) {
    document.body.scrollTop = 0;
    window.location.reload();
  });
}

function big_red_button() {
  lightbox('Bye, bye, data.', 'Please wait...');
  var uri = 'nuke';
  post(uri, function(xhr) {
    document.body.scrollTop = 0;
    window.location.reload();
  });
}

function createEditor(mime_type) {
  return CodeMirror(source_code, {
    value: 'Initializing...',
    mode: mime_type,
    lineNumbers: true,
    matchBrackets: true,
    undoDepth: 440, // default = 40
  });
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

resizer('divider1', 'source-container');
resizer('divider2', 'output-iframe');
