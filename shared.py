"""Module for shared playground functions."""

import httplib
import logging
import os

from mimic.__mimic import common
from mimic.__mimic import mimic

import error
from error import Abort
import settings

from google.appengine.api import app_identity
from google.appengine.api import backends
from google.appengine.api import users


# HTTP methods which do not affect state
_HTTP_READ_METHODS = ('GET', 'OPTIONS')


def e(msg, *args, **kwargs):
  if isinstance(msg, basestring):
    if args or kwargs:
      msg = msg.format(*args, **kwargs)
  raise RuntimeError(repr(msg))


def i(msg, *args, **kwargs):
  if isinstance(msg, basestring):
    if args or kwargs:
      msg = msg.format(*args, **kwargs)
  logging.info('@@@@@ {0}'.format(repr(msg)))


def w(msg, *args, **kwargs):
  if isinstance(msg, basestring):
    if args or kwargs:
      msg = msg.format(*args, **kwargs)
  logging.warning('##### {0}'.format(repr(msg)))


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
  return app_identity.get_application_id() == settings.PLAYGROUND_APP_ID


def IsHttpReadMethod(environ):
  return environ['REQUEST_METHOD'] in _HTTP_READ_METHODS


def AssertIsAdmin():
  if not users.is_current_user_admin():
    Abort(403, 'Admin only function')


def AssertHasProjectReadAccess(environ):
  """Assert that the current user has project read permissions.

  Args:
    environ: the current WSGI environ

  Returns:
    True if the current user as read access to the current project. When
    deployed as two collaborating app ids, as determined by
    settings.TWO_COLLABORATING_APP_IDS, always returns True.
  """
  project = environ['playground.project']
  if not project:
    Abort(httplib.NOT_FOUND, 'Project does not exist')
  access_key = environ.get(settings.ACCESS_KEY_HTTP_HEADER_WSGI, None)
  if access_key and access_key == project.access_key:
    return
  if users.is_current_user_admin():
    return
  user = environ.get('playground.user', None)
  if user and user.key.id() in project.writers:
    return
  if settings.PROJECT_TEMPLATE_OWNER in project.writers:
    return
  Abort(httplib.UNAUTHORIZED, 'Missing project read access')


def AssertHasProjectWriteAccess(environ):
  """Assert that the current user has project write permissions.

  Args:
    environ: the current WSGI environ

  Returns:
    True if the current user as write access to the current project.
  """
  project = environ['playground.project']
  if not project:
    Abort(httplib.NOT_FOUND, 'Project does not exist')
  if users.is_current_user_admin():
    return
  user = environ.get('playground.user')
  if user and user.key.id() in project.writers:
    return
  Abort(httplib.UNAUTHORIZED, 'Missing project write access')
