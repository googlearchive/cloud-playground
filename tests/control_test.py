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

"""Unit tests for control.py."""

import cStringIO
import httplib
import json
import logging
import re
import time
import urllib


# Import test_util first, to ensure python27 / webapp2 are setup correctly
from tests import test_util

from __mimic import common  # pylint: disable-msg=C6203
from __mimic import composite_query
from __mimic import control
from __mimic import datastore_tree

import unittest


_VERSION_STRING_FORMAT = """\
MIMIC
version_id=%s
"""


def _CreateFakeChannel(client_id):
  return 'token:%s' % client_id


class ControlAppTest(unittest.TestCase):
  """Test the app created by MakeControlApp."""

  def setUp(self, tree=None):
    test_util.InitAppHostingApi()
    self.setUpApplication(tree)
    # these are updated after StartResponse is called
    self._status = None
    self._headers = None
    self._output = ''

  def setUpApplication(self, tree=None):
    """Sets up the control application and its tree."""
    if tree:
      self._tree = tree
    else:
      self._tree = datastore_tree.DatastoreTree()
    self._application = control.MakeControlApp(
        self._tree, create_channel_fn=_CreateFakeChannel)

  def StartResponse(self, status, headers):
    """A WSGI start_response method."""
    self._status = status
    self._headers = dict(headers)
    self._output = ''
    return self.AccumulateOutput

  def AccumulateOutput(self, data):
    """Used by StartResponse to accumlate response data."""
    self._output += data

  def RunWSGI(self, path_query, post=None, form=False):
    """Invoke the application on a given path/query.

    Args:
      path_query: The path and optional query portion of the URL, for example
          /foo or /foo?x=123
      post: Optional data to be sent as the body of a POST (this also changes
          the REQUEST_METHOD from GET to POST).
      form: True indicates application/x-www-form-urlencoded should be used
          as the content type, otherwise the default of test/plain is used.
    """
    env = test_util.GetDefaultEnvironment()
    # setup path and query
    if '?' in path_query:
      path, query = path_query.split('?', 1)
      env['PATH_INFO'] = path
      env['QUERY_STRING'] = query
    else:
      env['PATH_INFO'] = path_query
    # handle POST data
    if post is not None:
      input_stream = cStringIO.StringIO(post)
      env['REQUEST_METHOD'] = 'POST'
      if form:
        env['CONTENT_TYPE'] = 'application/x-www-form-urlencoded'
      else:
        env['CONTENT_TYPE'] = 'text/plain'
      env['CONTENT_LENGTH'] = len(post)
      env['wsgi.input'] = input_stream
    # invoke the application
    response = self._application(env, self.StartResponse)
    for data in response:
      self.AccumulateOutput(data)

  def Check(self, status_code, output=None):
    """Check the results of invoking the application.

    Args:
      status_code: The expected numeric HTTP status code.
      output: The expected output, or None if output should not be checked.
    """
    actual = int(self._status.split(' ', 1)[0])
    self.assertEquals(status_code, actual)
    if output is not None:
      self.assertEquals(output, self._output)

  def testGetFileContents(self):
    self._tree.SetFile('foo.html', '123')
    self.RunWSGI('/_ah/mimic/file?path=foo.html')
    self.Check(httplib.OK, output='123')

  def testGetFileNotFound(self):
    self.RunWSGI('/_ah/mimic/file?path=foo.html')
    self.Check(httplib.NOT_FOUND)

  def testGetFileBadRequest(self):
    self.RunWSGI('/_ah/mimic/file')
    self.Check(httplib.BAD_REQUEST)

  def testSetFile(self):
    class MutableTree(object):
      def SetFile(self, path, contents):
        self.path = path
        self.contents = contents

      def IsMutable(self):
        return True

    self.setUpApplication(MutableTree())
    self.RunWSGI('/_ah/mimic/file?path=foo.html', post='abc')
    self.Check(httplib.OK)
    self.assertEqual(self._tree.contents, 'abc')
    self.assertEqual(self._tree.path, 'foo.html')

  def testSetFileBadRequest(self):
    self.RunWSGI('/_ah/mimic/file', post='123')
    self.Check(httplib.BAD_REQUEST)

  def testSetFileImmutable(self):
    class ImmutableTree(object):
      def IsMutable(self):
        return False

    self.setUpApplication(ImmutableTree())
    self.RunWSGI('/_ah/mimic/file?path=foo.html', post='abc')
    self.Check(httplib.BAD_REQUEST)

  def testClear(self):
    self.RunWSGI('/_ah/mimic/clear', post='')
    self.Check(httplib.OK)
    self.assertEquals([], self._tree.ListDirectory('/'))

  def testClearImmutable(self):
    class ImmutableTree(object):
      def IsMutable(self):
        return False

    self.setUpApplication(ImmutableTree())
    self.RunWSGI('/_ah/mimic/clear', post='')
    self.Check(httplib.BAD_REQUEST)

  def testLog(self):
    self.RunWSGI('/_ah/mimic/log')
    self.Check(httplib.OK)
    # output should have the logging token in it
    self.assertIn('"token:logging"', self._output)

  def testIndex(self):
    composite_query._RecordIndex('foo')
    composite_query._RecordIndex('bar')
    self.RunWSGI('/_ah/mimic/index')
    self.Check(httplib.OK, output="""indexes:

bar

foo""")
    self.RunWSGI('/_ah/mimic/index', post='')
    self.Check(httplib.OK, output="""indexes:

""")

  def testGetVersionId(self):
    self.RunWSGI('/_ah/mimic/version_id')
    self.Check(httplib.OK)
    expected = _VERSION_STRING_FORMAT % common.VERSION_ID
    self.assertEquals(expected, self._output)

  def testControlRequestRequiresTree(self):
    self.assertTrue(control.ControlRequestRequiresTree('/_ah/mimic/file'))
    self.assertTrue(control.ControlRequestRequiresTree('/_ah/mimic/clear'))
    self.assertFalse(control.ControlRequestRequiresTree('/user/file'))
    self.assertFalse(control.ControlRequestRequiresTree('/user/clear'))
    self.assertFalse(control.ControlRequestRequiresTree('/file'))


class LoggingHandlerTest(unittest.TestCase):
  def setUp(self):
    self._values = None
    self._handler = control.LoggingHandler(send_message_fn=self._SendMessage)

  def _SendMessage(self, client_id, message):
    # check the client_id, decode and save the message
    self.assertEquals(client_id, control._LOGGING_CLIENT_ID)
    self.assertIsNone(self._values)
    self._values = json.loads(message)

  def testNormal(self):
    before = time.time()
    record = logging.LogRecord('', logging.INFO, 'foo.py', 123, 'my message',
                               (), None)
    after = time.time()
    self._handler.handle(record)
    self.assertEquals('INFO', self._values['levelname'])
    self.assertEquals('my message', self._values['message'])
    created = self._values['created']
    self.assertTrue(before <= created and created <= after)

  def testLongMessage(self):
    message = 'this is a start' + ('1234567890' * 1000)
    self.assertTrue(len(message) > control._MAX_LOG_MESSAGE)
    record = logging.LogRecord('', logging.INFO, 'foo.py', 123, message,
                               (), None)
    self._handler.handle(record)
    expected = message[:control._MAX_LOG_MESSAGE]  # should be truncated
    self.assertEquals(expected, self._values['message'])


if __name__ == '__main__':
  unittest.main()
