"""Module for shared playground functions."""

import httplib
import logging
import mimetypes

from __mimic import common
from __mimic import mimic

import model
import settings

from google.appengine.api import app_identity
from google.appengine.api import namespace_manager
from google.appengine.api import urlfetch


def e(msg, *args, **kwargs):
  if isinstance(msg, basestring):
    msg = msg.format(*args, **kwargs)
  raise Exception(repr(msg))


def w(msg, *args, **kwargs):
  if isinstance(msg, basestring):
    msg = msg.format(*args, **kwargs)
  logging.warning('##### {0}'.format(repr(msg)))


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


def Fetch(url, follow_redirects=False, async=False):
  """Make an HTTP request using URL Fetch."""
  rpc = urlfetch.create_rpc()
  urlfetch.make_fetch_call(rpc, url,
                           follow_redirects=follow_redirects,
                           validate_certificate=True)
  if async:
    return rpc
  response = rpc.get_result()
  if response.status_code != httplib.OK:
    e('Status code {0} fetching {1} {2}', response.status_code, url,
      response.content)
  return response


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


def ThisIsPlaygroundApp():
  """Determines whether this is the playground app id."""
  if common.IsDevMode():
    return True
  return app_identity.get_application_id() == settings.PLAYGROUND_APP_ID


def DoesCurrentProjectExist():
  """Checks whether the curent project exists."""
  project_id = mimic.GetProjectId()
  if not project_id:
    return None
  prj = model.GetProject(project_id)
  if not prj:
    return None
  assert namespace_manager.get_namespace() == project_id, (
      'namespace_manager.get_namespace()={0!r}, project_id={1!r}'
      .format(namespace_manager.get_namespace(), project_id))
  return True
