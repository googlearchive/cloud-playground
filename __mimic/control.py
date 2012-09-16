#!/usr/bin/env python
#
# Copyright 2012 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""A simple web application to control Mimic."""



import httplib
import json
import logging
import os

from __mimic import common
from __mimic import composite_query

from google.appengine.api import channel
from google.appengine.ext import webapp


_CONTROL_PATHS_REQUIRING_TREE = [
    common.CONTROL_PREFIX + '/clear',
    common.CONTROL_PREFIX + '/file'
    ]
_LOGGING_CLIENT_ID = 'logging'
_MAX_LOG_MESSAGE = 1024  # will keep the channel message under the 32K Limit


class _TreeHandler(webapp.RequestHandler):
  """Base class for RequestHandlers that require a Tree object."""

  def __init__(self, request, response):
    """Initializes this request handler with the given Request and Response."""
    webapp.RequestHandler.initialize(self, request, response)
    self._tree = self.app.config.get('tree')


class _ClearHandler(_TreeHandler):
  """Handler for clearing all files."""

  def post(self):  # pylint: disable-msg=C6409
    """Clear all files."""
    if self._tree.IsMutable():
      self._tree.Clear()
    else:
      self.error(httplib.BAD_REQUEST)


class _FileHandler(_TreeHandler):
  """Handler for getting/setting files."""

  def get(self):  # pylint: disable-msg=C6409
    """Get a file's contents."""
    self.response.headers['Content-Type'] = 'text/plain'
    path = self.request.get('path')
    if not path:
      self.error(httplib.BAD_REQUEST)
      return
    data = self._tree.GetFileContents(path)
    if data is None:
      self.error(httplib.NOT_FOUND)
      return
    self.response.out.write(data)

  def post(self):  # pylint: disable-msg=C6409
    """Set a file's contents."""
    path = self.request.get('path')
    if not path or not self._tree.IsMutable():
      self.error(httplib.BAD_REQUEST)
      return
    self._tree.SetFile(path, self.request.body)


class _IndexHandler(webapp.RequestHandler):
  """Handler for getting index.yaml definitions.

  GET: returns the auto-generated index.yaml contents.
  POST: clears the auto-generated index.yaml contents.
  """

  def get(self):  # pylint: disable-msg=C6409
    self.response.headers['Content-Type'] = 'text/plain'
    # TODO: composite_query._RecordIndex() records the app's index
    # yaml in the munged (ie, project-name-prefixed) namespace, so _IndexHandler
    # must read from that namespace. Likely the right thing to do here is to
    # separate the datastore patches into their own unit that can be installed
    # separately from the target_env, rather than manaully prefix the namespace
    # here.
    self.response.out.write(composite_query.GetIndexYaml())

  def post(self):  # pylint: disable-msg=C6409
    # clear and then return the cleared index spec
    composite_query.ClearIndexYaml()
    self.get()


class _LogRequestHandler(webapp.RequestHandler):
  """Handler for realtime logging."""

  def __init__(self, request, response):
    """Initializes this request handler with the given Request and Response."""
    webapp.RequestHandler.initialize(self, request, response)
    self._create_channel_fn = self.app.config.get('create_channel_fn')

  def get(self):  # pylint: disable-msg=C6409, C6111
    parent = os.path.dirname(__file__)
    path = os.path.join(parent, 'templates', 'log.html')
    data = open(path).read()
    token = self._create_channel_fn(_LOGGING_CLIENT_ID)
    values = {
        'token': token,
    }
    # TODO: It would probably be safer to use real templating instead
    # of string interpolation, but that would require additional code to
    # separate mimic and the client's use of the template cache.
    self.response.out.write(data % values)


# TODO: It may be better to collect all log records during script
# execution and only send them back after the script is complete.  Multiple
# log records could be bundled together for efficiency, and there would be no
# concern over nested logging calls.  The disadvantage is that this sort of
# mechanism would be useless in debugging scripts that take too long to
# execute since the entire script would have timed out before there was any
# chance to send the log records back.


class LoggingHandler(logging.Handler):
  """A logging.LogHandler that sends log messages over a channel."""

  def __init__(self, send_message_fn=channel.send_message):
    logging.Handler.__init__(self)
    self._send_message_fn = send_message_fn
    self._sending = False  # prevent recursive logging

  def emit(self, record):
    """Emit a log message (see documentation for the logging module)."""
    if self._sending:
      # we don't want logging calls from within emit() to trigger another
      # log message, so ignore any nested logging calls
      return

    self._sending = True
    values = {
        'created': record.created,
        'levelname': record.levelname,
        'message': record.getMessage()[:_MAX_LOG_MESSAGE],
    }
    encoded = json.dumps(values)
    self._send_message_fn(_LOGGING_CLIENT_ID, encoded)
    self._sending = False


class _VersionIdHandler(webapp.RequestHandler):
  """Handler that returns the version ID of this mimic."""

  def get(self):  # pylint: disable-msg=C6409, C6111
    self.response.headers['Content-Type'] = 'text/plain'
    self.response.headers['Access-Control-Allow-Origin'] = '*'
    self.response.out.write('MIMIC\n')
    self.response.out.write('version_id=%s\n' % str(common.VERSION_ID))


def ControlRequestRequiresTree(path_info):
  """Determines if the control request (by path_info) requires a Tree."""
  for handler_path in _CONTROL_PATHS_REQUIRING_TREE:
    if path_info.startswith(handler_path):
      return True
  return False


def MakeControlApp(tree, create_channel_fn=channel.create_channel):
  """Create and return a WSGI application for controlling Mimic."""
  # standard handlers
  handlers = [
      ('/clear', _ClearHandler),
      ('/file', _FileHandler),
      ('/index', _IndexHandler),
      ('/log', _LogRequestHandler),
      ('/version_id', _VersionIdHandler),
      ]
  # prepend CONTROL_PREFIX to all handler paths
  handlers = [(common.CONTROL_PREFIX + p, h) for (p, h) in handlers]
  config = {'tree': tree, 'create_channel_fn': create_channel_fn}
  return webapp.WSGIApplication(handlers, debug=True, config=config)
