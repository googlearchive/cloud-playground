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

"""An App Engine application that is a reference test for Mimic.

This application invokes unit tests while running within the App Engine
servers.  It can be deployed as a normal App Engine app to verify that
the tests are consistent with real App Engine behavior.  It can then be
run via Mimic to verify that Mimic matches App Engine's native behavior.
"""



import cStringIO
import sys
import unittest

from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app

# Each test file should be imported here and added to _TEST_MODULES
import datastore_test
import file_test
import import_test
import os_test

_TEST_MODULES = [datastore_test, file_test, import_test, os_test]


def CreateTestSuite():
  """Create a test suite that includes all of the test modules."""
  loader = unittest.defaultTestLoader
  suite = unittest.TestSuite()
  for module in _TEST_MODULES:
    suite.addTest(loader.loadTestsFromModule(module))
    # run module setUp function (if defined)
    if hasattr(module, 'setUp'):
      getattr(module, 'setUp')()
  return suite


class MainTestPageHandler(webapp.RequestHandler):
  """A RequestHandler that runs the tests and prints the results."""

  def get(self):  # pylint: disable-msg=C6409
    """Handle HTTP GET requests."""
    self.response.headers['Content-Type'] = 'text/plain'
    output = cStringIO.StringIO()
    saved_output = sys.stdout
    try:
      sys.std_output = output
      runner = unittest.TextTestRunner(output)
      suite = CreateTestSuite()
      runner.run(suite)
    finally:
      sys.stdout = saved_output
    self.response.write(output.getvalue())


application = webapp.WSGIApplication([
    ('/', MainTestPageHandler)
    ], debug=True)


def main():
  run_wsgi_app(application)


if __name__ == '__main__':
  main()
