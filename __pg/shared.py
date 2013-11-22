"""Module for shared playground functions."""

import httplib
import logging
import os

from mimic.__mimic import common

from . import appids
from error import Abort
from . import settings

from google.appengine.api import app_identity
from google.appengine.api import backends
from google.appengine.api import users
from google.appengine.api import urlfetch


# default URLFetch deadline
_URL_FETCH_DEADLINE = 3


# HTTP methods which do not affect state
_HTTP_READ_METHODS = ('GET', 'OPTIONS')


def e(msg, *args, **kwargs):  # pylint:disable-msg=invalid-name
  if isinstance(msg, basestring):
    if args or kwargs:
      msg = msg.format(*args, **kwargs)
  raise RuntimeError(repr(msg))


def i(msg, *args, **kwargs):  # pylint:disable-msg=invalid-name
  if isinstance(msg, basestring):
    if args or kwargs:
      msg = msg.format(*args, **kwargs)
  logging.info('@@@@@ {0}'.format(repr(msg)))


def w(msg, *args, **kwargs):  # pylint:disable-msg=invalid-name
  if isinstance(msg, basestring):
    if args or kwargs:
      msg = msg.format(*args, **kwargs)
  logging.warning('##### {0}'.format(repr(msg)))


def Fetch(access_key, url, method, payload=None, deadline=_URL_FETCH_DEADLINE,
          retries=1):
  for i in range(0, retries):
    try:
      headers = {settings.ACCESS_KEY_HTTP_HEADER: access_key}
      return urlfetch.fetch(url, headers=headers, method=method,
                            payload=payload, follow_redirects=False,
                            deadline=deadline)
    except e:
      if i == retries - 1:
        raise
      w('Will retry {} {} which encountered {}'.format(method, url, e))


def GetCurrentTaskName():
  return os.environ.get('HTTP_X_APPENGINE_TASKNAME')


def EnsureRunningInTask():
  """Ensures that we're currently executing inside a task.

  Raises:
    RuntimeError: when not executing inside a task.
  """
  if GetCurrentTaskName():
    return
  raise RuntimeError('Not executing in a task queue')


def ThisIsPlaygroundApp():
  """Determines whether this is the playground app id."""
  if common.IsDevMode():
    return not backends.get_backend()
  return app_identity.get_application_id() == appids.PLAYGROUND_APP_ID


def IsHttpReadMethod(environ):
  return environ['REQUEST_METHOD'] in _HTTP_READ_METHODS


def AssertIsAdmin():
  if not users.is_current_user_admin():
    Abort(403, 'Admin only function')


def HasProjectReadAccess(environ):
  """Assert that the current user has project read permissions.

  Args:
    environ: the current WSGI environ

  Returns:
    True if the current user has read access to the current project.
  """
  project = environ['playground.project']
  if not project:
    Abort(httplib.NOT_FOUND, 'requested read access to non-existent project')
  access_key = environ.get('mimic.access_key')
  if access_key and access_key == project.access_key:
    return True
  if users.is_current_user_admin():
    return True
  user = environ.get('playground.user', None)
  if user and user.key.id() in project.writers:
    return True
  if settings.PUBLIC_PROJECT_TEMPLATE_OWNER in project.writers:
    return True
  if settings.MANUAL_PROJECT_TEMPLATE_OWNER in project.writers:
    return True
  return False


def HasProjectWriteAccess(environ):
  """Assert that the current user has project write permissions.

  Args:
    environ: the current WSGI environ

  Returns:
    True if the current user as write access to the current project.
  """
  project = environ['playground.project']
  if not project:
    Abort(httplib.NOT_FOUND, 'requested write access to non-existent project')
  if users.is_current_user_admin():
    return True
  user = environ.get('playground.user')
  if user and user.key.id() in project.writers:
    return True
  return False
