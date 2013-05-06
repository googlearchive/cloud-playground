"""Module for shared playground functions."""

import httplib
import logging
import os

from mimic.__mimic import common
from mimic.__mimic import mimic

import model
import settings

from google.appengine.api import app_identity
from google.appengine.api import namespace_manager
from google.appengine.api import urlfetch


# 10 minutes
MEMCACHE_TIME = 3600


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


class FetchError(urlfetch.Error):
  """URL Fetch error for response code != 200."""

  def __init__(self, url, response):
    self.url = url
    self.response = response

  def __str__(self):
    return 'Status code {0} fetching {1} {2}'.format(self.response.status_code,
                                                     self.url,
                                                     self.response.content)

def GetCurrentTaskName():
  return os.environ.get('HTTP_X_APPENGINE_TASKNAME')


def EnsureRunningInTask():
  """Ensures that we're currently executing inside a task.

  If not, raise a RuntimeError.
  """
  if GetCurrentTaskName():
    return
  raise RuntimeError('Not executing in a task queue')


def Fetch(url, follow_redirects=False, async=False, headers={}):
  """Make an HTTP request using URL Fetch."""
  rpc = urlfetch.create_rpc()
  urlfetch.make_fetch_call(rpc, url, headers=headers,
                           follow_redirects=follow_redirects,
                           validate_certificate=True)
  if async:
    return rpc
  response = rpc.get_result()
  if response.status_code != httplib.OK:
    raise FetchError(url, response)
  return response


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
