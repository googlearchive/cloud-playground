// DO THIS FIRST; REPLACE LATER
window.onerror = function(msg, url, line) {
  alert("JavaScript error on line " + line + " of " + url + "\n\n" + msg);
}

// Globals
var _files = {};
var _current_filename_id;
var _whoami = {};
var _dirty = false;
var _save_timeout;
var _editor;
var _output_window;
var _popout = false;

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
    var csrf = get_cookie('csrf');
    xhr.setRequestHeader('X-Bliss-CSRF', csrf);
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

// GET
function get(url, callback, data) {
  xhr('GET', url, function(xhr) {
    callback(xhr);
  }, data);
}

// POST
function post(url, callback, data) {
  xhr('POST', url, function(xhr) {
    callback(xhr);
  }, data);
}

// PUT
function put(url, callback, data) {
  xhr('PUT', url, function(xhr) {
    callback(xhr);
  }, data);
}

// JSON XHR
function json(url, callback, data) {
  get(url, function(xhr) {
    var content_type = xhr.getResponseHeader('Content-Type');
    if (content_type != 'application/json') {
      throw url + '\nReturned non-JSON Content-Type: ' + content_type;
    }
    try {
      eval('r = ' + xhr.responseText);
    } catch(e) {
      throw url + '\nFailed to eval JSON:\n' + xhr.responseText;
    }
    callback(xhr, r);
  }, data);
}

// CodeMirror helper
function getSelectedRange() {
  return { from: _editor.getCursor(true), to: _editor.getCursor(false) };
}

function insertAfter(newNode, existingNode) {
  var parentNode = existingNode.parentNode;
  if (existingNode.nextSibling) {
    return parentNode.insertBefore(newNode, existingNode.nextSibling);
  } else {
    return parentNode.appendChild(newNode);
  }
}

function file_context_menu(evt, id) {
  evt.stopPropagation();
  var menuDiv = document.getElementById('file-context-menu');
  menuDiv.style.display = 'block';
  menuDiv.style.left = evt.pageX + 'px';
  menuDiv.style.top = evt.pageY + 'px';
  var elem = document.getElementById(id);
  insertAfter(menuDiv, elem);
}

// activate a new file in the left nav
function selectFile(id) {
  if (_current_filename_id) {
    if (id == _current_filename_id) {
      return;
    }

    // CSS deselect previous file
    var elem = document.getElementById(_current_filename_id);
    elem.setAttribute('class', elem.getAttribute('class').replace(' selected', ' unselected'));

    // save file content
    save();

    // hide current file
    source_container.setAttribute('class', 'unknown');
  }

  // CSS select current file
  var elem = document.getElementById(id);
  if (elem) {
    elem.setAttribute('class', elem.getAttribute('class').replace(' unselected', ' selected'));
  }

  // remember current file
  _current_filename_id = id;

  // fetch file content
  var filename = _files[id];
  source_filename.innerHTML = filename;
  var uri = '/bliss/p/' + encodeURI(_whoami.project_name) + '/getfile/' + encodeURI(filename);
  get(uri, function(xhr) {
    // e.g. 'text/html; charset=UTF-8'
    var mime_type = xhr.getResponseHeader('Content-Type');
    // strip '; charset=...'
    mime_type = mime_type.replace(/ ?;.*/, '');
    if (/^image\//.test(mime_type)) {
      source_image.setAttribute('src', uri);
      source_container.setAttribute('class', 'image');
    } else {
      while(source_code.hasChildNodes()) {
        source_code.removeChild(source_code.childNodes[0]);
      }
      _editor = createEditor(mime_type);
      _editor.getScrollerElement().id = 'scroller-element';
      source_container.setAttribute('class', 'code');
      _editor.setValue(xhr.responseText);
      _editor.setOption('onChange', editorOnChange);
      _editor.focus();
    }
  });
}

function addfile(id, filename) {
  _files[id] = filename;
  var filelist = document.getElementById('filelist');
  var node = document.createElement('div');
  node.id = id;
  node.setAttribute('class', 'fileentry unselected');
  var url = 'http://' + _whoami.hostname + filename;
  node.innerHTML = '<span class="filename">' + filename + '</span><span class="dropdown"><a onclick="file_context_menu(arguments[0] || window.event, \'' + id + '\')">&hellip;</a></span>';
  filelist.insertBefore(node, filelist.lastChild);
}

function prompt_file_delete() {
  var filename = _files[_current_filename_id];
  var answer = prompt("Are you sure you want to delete " + filename + "?\nType 'yes' to confirm.", "no");
  if (!answer || answer.toLowerCase()[0] != 'y') {
    return;
  }
  var uri = 'deletepath/' + encodeURI(filename);
  post(uri, function(xhr) {
    document.body.scrollTop = 0;
    window.location.reload();
  });
}

function prompt_file_rename() {
  var filename = _files[_current_filename_id];
  var new_filename = prompt(
      'New filename?\n(You may specify a full path such as: foo/bar.txt)',
      filename);
  if (!new_filename) {
    return;
  }
  if (new_filename[0] == '/') {
    new_filename = new_filename.substr(1);
  }
  if (!new_filename || new_filename == filename) {
    return;
  }
  var uri = 'movefile/' + encodeURI(filename);
  var data = 'newpath=' + encodeURI(new_filename);
  post(uri, function(xhr) {
    document.body.scrollTop = 0;
    window.location.reload();
  }, data);
}

function prompt_for_new_project(template_url) {
  var project_name = prompt("Please select a unique project name.\nUse only lowercase letters (a-z), digits (0-9) and dashes (-).", "");
  if (!project_name) {
    return;
  }
  // var project_description = prompt('Project description', project_name) || project_name;
  var project_description = project_name;
  var uri = '/bliss/p/' + encodeURI(project_name) + '/create';
  var data = 'template_url=' + encodeURI(template_url) +
            '&project_description=' + encodeURI(project_description);
  box = lightbox(escape(project_description), 'Creating project. Please wait.');
  post(uri, function(xhr) {
    box();
    document.body.scrollTop = 0;
    window.location.reload();
  }, data);
}

function prompt_to_delete_project(project_name) {
  var answer = prompt("Are you sure you want to delete project " +
                      project_name + "?\nType 'yes' to confirm.", "no");
  if (!answer || answer.toLowerCase()[0] != 'y') {
    return;
  }
  var uri = '/bliss/p/' + encodeURI(project_name) + '/delete';
  post(uri, function(xhr) {
    document.body.scrollTop = 0;
    window.location.reload();
  });
}

function prompt_for_new_file() {
  var filename = prompt('New filename?', '');
  if (!filename) {
    return;
  }
  if (filename[0] == '/') {
    filename = filenamei
  }
  for (id in _files) {
    if (filename == _files[id]) {
      selectFile(id);
      return;
    }
  }
  var id = 'file-' + Object.keys(_files).length;
  var uri = '/bliss/p/' + encodeURI(_whoami.project_name) + '/putfile/' + encodeURI(filename);
  put(uri, function(xhr) {
    addfile(id, filename);
    selectFile(id);
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

function popout() {
  _popout = true;
  _output_window = undefined;
}

function run(url, project_name) {
  var container = document.getElementById('output-container');
  if (_output_window && _output_window.closed) {
    _popout = false;
  }
  if (_popout) {
    container.style.display = 'none';
    _output_window = window.open(url, project_name);
  } else {
    container.style.display = 'block';
    var container = document.getElementById('output-container');
    var where = document.getElementById('output-url');
    var iframe = document.getElementById('output-iframe');
    iframe.src = url;
    where.innerHTML = iframe.src;
  }
}

// populate left nav with list of filenames
function populateFilenames(filenames) {
  var filelist = document.getElementById('filelist');

  // allow the creation of new files
  var node =  document.createElement('div');
  node.setAttribute('class', 'newthing link');
  node.innerHTML = '+ new file';
  node.onclick = function(evt) {
    prompt_for_new_file();
  }
  filelist.appendChild(node);

  // add project files
  for (var i in filenames) {
    var id = 'file-' + i;
    var filename = filenames[i];
    addfile(id, filename);
  }
}

// initalize workspace
function initWorkspace() {
  json('whoami', function(xhr, r) {
    _whoami = r;
    initLeftNavClickHandler();
    initFileContextMenuClearHandler();
    json('listfiles/', function(xhr, files) {
      populateFilenames(files);
      if (files.length) {
        // select a file
        selectFile('file-0');
      }
    });
  });
}

// given an element in the left nav, determine the file id
function getFileIdFromElem(elem) {
  while (elem != null && elem.nodeName != 'BODY') {
    var clazz = elem.getAttribute('class');
    if (clazz && clazz.indexOf('fileentry') != -1) {
      return elem.id;
    }
    elem = elem.parentNode;
  }
  return null;
}

// setup file context menu clear handler
function initFileContextMenuClearHandler() {
  window.addEventListener('click', function(evt) {
    document.getElementById('file-context-menu').style.display = 'None';
  }, false);
}

// setup left nav click handler
function initLeftNavClickHandler() {
  nav.addEventListener('click', function(evt) {
    var id = getFileIdFromElem(evt.srcElement || evt.target);
    if (id) {
      selectFile(id);
    }
  }, true);
}

// called from setTimeout after editor is marked dirty
function save() {
  if (!_dirty) {
    return;
  }

  // TODO: fix me
  _dirty = false;

  // determine filename
  var filename = _files[_current_filename_id];

  set_status('Saving...');

  // TODO: catch exception and mark dirty
  var uri = '/bliss/p/' + encodeURI(_whoami.project_name) + '/putfile/' + encodeURI(filename);
  put(uri, function(xhr) {
    set_status(); // Saved
  }, _editor.getValue());
}

function markDirty() {
  if (_save_timeout) {
    return;
  }
  _dirty = true;
  _save_timeout = setTimeout(function() {
    _save_timeout = null;
    save();
  }, 1000);
}

// editor onChange
function editorOnChange(from, to, text, next) {
   markDirty();
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
    var newheight = initialheight + (evt.y - downy);
    elem.style.height = newheight + 'px';
  };

  var downfunc = function(evt) {
    evt.preventDefault();
    isdown = true;
    downx = evt.x;
    downy = evt.y;
    elem = document.getElementById(content_id);
    initialheight = elem.offsetHeight;
    dragDiv.style.display = 'block';
    dragDiv.addEventListener('mousemove', movefunc);
    dragDiv.addEventListener('mouseup', upfunc);
  };

  var upfunc = function(evt) {
    isdown = false;
    dragDiv.style.display = 'none';
    dragDiv.removeEventListener(movefunc);
    dragDiv.removeEventListener(upfunc);
  };

  divider.addEventListener('mousedown', downfunc);
}

resizer('divider1', 'scroller-element');
resizer('divider2', 'output-iframe');
