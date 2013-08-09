"""Module for shared playground functions."""

import logging
import os

from mimic.__mimic import common
from mimic.__mimic import mimic

import error
from error import *
import settings

from google.appengine.api import app_identity
from google.appengine.api import namespace_manager
from google.appengine.api import users


# RFC1113 formatted 'Expires' to prevent HTTP/1.0 caching
LONG_AGO = 'Mon, 01 Jan 1990 00:00:00 GMT'

# 10 minutes
MEMCACHE_TIME = 3600

# Owner of template projects
TEMPLATE_OWNER = 'TEMPLATE'

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

  If not, raise a RuntimeError.
  """
  if GetCurrentTaskName():
    return
  raise RuntimeError('Not executing in a task queue')


def ThisIsPlaygroundApp(environ):
  """Determines whether this is the playground app id."""
  if common.IsDevMode():
    return environ['HTTP_HOST'] in settings.PLAYGROUND_HOSTS
  return app_identity.get_application_id() == settings.PLAYGROUND_APP_ID


def IsHttpReadMethod(environ):
  return environ['REQUEST_METHOD'] in _HTTP_READ_METHODS


def AssertIsAdmin():
  if not users.is_current_user_admin():
    Abort(403, 'Admin only function')


def AssertHasProjectReadAccess(environ):
  #if 'playground.project' not in environ:
  #  Abort(httplib.BAD_REQUEST, 'Unable to determine project from URL')
  user = environ['playground.user']
  project = environ['playground.project']
  if not project:
    Abort(httplib.NOT_FOUND, 'Project does not exist')
  if users.is_current_user_admin():
    return
  if user.key.id() in project.writers:
    return
  if TEMPLATE_OWNER in project.writers:
    return
  Abort(httplib.UNAUTHORIZED, 'Not authorized to access this project')


def AssertHasProjectWriteAccess(environ):
  user = environ['playground.user']
  project = environ['playground.project']
  if not project:
    Abort(httplib.NOT_FOUND, 'Project does not exist')
  if users.is_current_user_admin():
    return
  if user.key.id() in project.writers:
    return
  Abort(httplib.UNAUTHORIZED, 'Not authorized to access this project')
