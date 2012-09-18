import logging
import os
import re

import mimetypes
import model

from google.appengine.api import users
from google.appengine.api import namespace_manager


from __mimic import datastore_tree

_PROJECT_NAME_FROM_PATH_INFO_RE = re.compile('/bliss/p/(.+?)/')
_PROJECT_NAME_FROM_HOSTNAME_RE = re.compile('(.+?)-dot-(.+?)\.')

# Namepsace valid re: ^[0-9A-Za-z._-]{0,100}$
_NAMESPACE_RE = re.compile('^[^0-9A-Za-z._-]$')

# namespace for bliss specific data
_BLISS_NAMESPACE = '_bliss'

# dev_appserver cookie, used to set the default project, which
# makes life easier in the absence of project-specific hostnames
BLISS_PROJECT_NAME_COOKIE = '_bliss_project'

# Extensions to exclude when creating template projects
_SKIP_EXTENSIONS = ('swp','pyc','svn')


def e(msg, *args, **kwargs):
  if isinstance(msg, basestring):
    msg = msg.format(*args, **kwargs)
  raise Exception(repr(msg))


def w(msg, *args, **kwargs):
  if isinstance(msg, basestring):
    msg = msg.format(*args, **kwargs)
  logging.warning('##### {0}'.format(repr(msg)))


def IsDevAppserver():
  return os.environ['SERVER_SOFTWARE'].startswith('Development/')


# TODO: use the MIME Type list at http://codemirror.net/
_TEXT_MIME_TYPES = {
  'css': 'text/css',
  # *.dart uses *.js MIME Type for now
  'dart': 'text/javascript',
  'html': 'text/html',
  'js': 'text/javascript',
  'jsp': 'application/x-jsp',
  'json': 'application/json',
  'php': 'application/x-httpd-php',
  'sh': 'text/x-sh',
  'sql': 'text/x-mysql',
  'xml': 'application/xml',
  'yaml': 'text/x-yaml',
}


def IsTextMimeType(mime_type):
  return mime_type.startswith('text/') or mime_type in _TEXT_MIME_TYPES.values()


def GetExtension(filename):
  return filename.lower().split('.')[-1]


def GuessMimeType(filename):
  """Guess the MIME Type based on the provided filename."""
  extension = GetExtension(filename)
  if extension in _TEXT_MIME_TYPES:
    return _TEXT_MIME_TYPES[extension]
  mime_type, _ = mimetypes.guess_type(filename)
  if not mime_type:
    logging.warning('Failed to guess MIME Type for "%s" with extension "%s"',
                    filename, extension)
    # TODO: remove once production App Engine does not return (None, None) for
    # import mimetypes; mimetypes.guess_type('favicon.ico')
    if extension == 'ico':
      mime_type = 'image/x-icon'
  if mime_type:
    return mime_type
  return 'text/plain'


def GetProjectNameFromCookie():
  if 'HTTP_COOKIE' not in os.environ:
    return None
  cookies = dict([c.split('=') for c in os.environ['HTTP_COOKIE'].split('; ')])
  return cookies.get(BLISS_PROJECT_NAME_COOKIE)


def project_name_from_path_info(path_info):
  m = _PROJECT_NAME_FROM_PATH_INFO_RE.match(path_info)
  if not m:
    return None
  return m.group(1)


def project_name_from_hostname(hostname):
  m = _PROJECT_NAME_FROM_HOSTNAME_RE.match(hostname)
  if not m:
    return None
  return m.group(1)


def GetProjectName():
  # For task queues, use persisted namespace as the project
  if 'HTTP_X_APPENGINE_CURRENT_NAMESPACE' in os.environ:
    return os.environ['HTTP_X_APPENGINE_CURRENT_NAMESPACE']
  project_name = project_name_from_path_info(os.environ['PATH_INFO'])
  if project_name:
    return project_name
  project_name = project_name_from_hostname(os.environ['SERVER_NAME'])
  if project_name:
    return project_name
  # for non-bliss admin pages dev_appserver determines project via a cookie
  if (IsDevAppserver() and
      not os.environ['PATH_INFO'].startswith('/bliss/')):
    project_name = GetProjectNameFromCookie()
  return project_name


def GetNamespace():
  project_name = GetProjectName()
  if not project_name:
    return None
  # TODO: check project_name at creation time
  if _NAMESPACE_RE.match(project_name):
    e('Invalid namespace %s' % project_name)
  return project_name


def DoesCurrentProjectExist():
  project_name = GetProjectName()
  if not project_name:
    return None
  prj = model.GetProject(project_name)
  if not prj:
    return None
  assert namespace_manager.get_namespace() == project_name
  return True
