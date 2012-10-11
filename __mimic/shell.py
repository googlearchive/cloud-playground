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

"""Handles executing a python script file within the target environment context.

  FileHandler: Request handler that executes a python script.
"""



import logging
import sys

from __mimic import common
from __mimic import target_env

from google.appengine.ext import webapp


class FileHandler(webapp.RequestHandler):
  """Executes a python script within a target_env context.

  GET: Executes a python script and optionally a specific function
  """

  def __init__(self, request, response):
    """Initializes this request handler with the given Request and Response."""
    webapp.RequestHandler.initialize(self, request, response)
    tree = self.app.config.get('tree')
    namespace = self.app.config.get('namespace')
    self.env = target_env.TargetEnvironment(tree, None, namespace)

  def get(self):  # pylint: disable-msg=C6409
    """Executes a file non-interactively printing the result to response.out."""
    self.response.headers['Content-Type'] = 'text/plain'
    path = self.request.get('path')
    if not path:
      return

    # os.path.join in ResolvePath will freak out if our file starts with a '/'
    # so we just strip off the leading '/' if any.
    path = path.strip('/')
    logging.info('Executing Python file %s', path)

    # Redirect stdout and stderr to the response stream
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    try:
      sys.stdout = self.response.out
      sys.stderr = self.response.out
      self.env.RunScript(path, None, self.request.get('function'))
    except target_env.ScriptNotFoundError:
      self.error(404)
      self.response.out.write('Script not found: ' + path)
    except target_env.TargetAppError, e:
      self.error(500)
      self.response.out.write(str(e))
    finally:
      sys.stdout = old_stdout
      sys.stderr = old_stderr


def MakeShellApp(tree, namespace):
  """Create and return a WSGI application for controlling Mimic."""
  # standard handlers
  handlers = [
      ('/python/file', FileHandler),
      ]
  # prepend CONTROL_PREFIX to all handler paths
  handlers = [(common.SHELL_PREFIX + p, h) for (p, h) in handlers]
  config = {'tree': tree, 'namespace': namespace}
  return webapp.WSGIApplication(handlers, debug=True, config=config)
