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

"""This script runs all the unittests.

See README.txt for usage.
"""

import os
import sys

import unittest

try:
  import dev_appserver
except ImportError:

  error_msg = ('The path to the App Engine Python SDK must be in the '
               'PYTHONPATH environment variable to run unittests.')

  # The app engine SDK isn't in sys.path. If we're on Windows, we can try to
  # guess where it is.
  import platform
  if platform.system() == 'Windows':
    sys.path.append('C:\\Program Files\\Google\\google_appengine')
    try:
      import dev_appserver  # pylint: disable-msg=C6204
    except ImportError:
      print error_msg
      raise
  else:
    print error_msg
    raise

DIR_PATH = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))


def main():

  # add app engine libraries
  sys.path.extend(dev_appserver.EXTRA_PATHS)

  if len(sys.argv) == 2:
    file_pattern = sys.argv[1]
  else:
    file_pattern = '*_test.py'

  # setup a minimal / partial CGI environment
  os.environ['SERVER_NAME'] = 'localhost'
  os.environ['SERVER_SOFTWARE'] = 'Development/unittests'
  os.environ['PATH_INFO'] = '/moonbase'

  argv = ['', 'discover',
          '-v',  # verbose
          '-s', DIR_PATH,  # search path
          '-p', file_pattern  # test file pattern
         ]
  unittest.main(argv=argv)

if __name__ == '__main__':
  main()
