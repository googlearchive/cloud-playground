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

"""Unit tests for shell.py."""



import cStringIO
import httplib

# Import test_util first, to ensure python27 / webapp2 are setup correctly
from tests import test_util

from __mimic import common  # pylint: disable-msg=C6203
from __mimic import datastore_tree
from __mimic import shell

import unittest


class ShellAppTest(unittest.TestCase):
  """Test the app created by MakeShellApp."""

  def setUp(self):
    test_util.InitAppHostingApi()
    self._tree = datastore_tree.DatastoreTree()
    self._application = shell.MakeShellApp(self._tree, 'TEST')
    # these are updated after StartResponse is called
    self._status = None
    self._headers = None
    self._output = ''

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

  def testRunFile(self):
    self._tree.SetFile('test.py', 'print "test"')
    self.RunWSGI('/_ah/shell/python/file?path=test.py')
    self.Check(httplib.OK, 'test\n')

  def testRunFileWithMainCode(self):
    self._tree.SetFile('test.py', """
def test():
  print 'test'""")
    self.RunWSGI('/_ah/shell/python/file?path=test.py&function=test()')
    self.Check(httplib.OK, 'test\n')

  def testTargetAppError(self):
    self._tree.SetFile('test.py', 'raise AttributeError')
    self.RunWSGI('/_ah/shell/python/file?path=test.py')
    self.Check(httplib.INTERNAL_SERVER_ERROR)


if __name__ == '__main__':
  unittest.main()
