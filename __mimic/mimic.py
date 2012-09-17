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

"""Application logic for Mimic.

The Mimic application must serve two distinct types of requests:

* Control requests are used to interact with Mimc and are handled internally.
* Target requests represent the user's application and processed according
  to the files retrieved from the datastore.

The target application may include Python code which will expect to run
in a pristine environment, so measures are taken not to invoke any sort of
WSGI framework until it is determined that the request is a control request.
"""

import httplib
import logging
import mimetypes
import os
import sys


from __mimic import common
from __mimic import control
from __mimic import datastore_tree
from __mimic import shell
from __mimic import target_env
from __mimic import target_info
import yaml

# import parts of the google.appengine.api.appinfo package (extracted from the
# local SDK by sdkapi.sh), since the appinfo package is currently unavailable in
# the App Engine production environment
from sdkapi import appinfo
from google.appengine.api import app_identity
from google.appengine.api import users
from google.appengine.ext.webapp.util import run_wsgi_app

# os.environ key representing 'X-AppEngine-QueueName' HTTP header,
# which should only be present for 'offline' task queue requests,
# see https://developers.google.com/appengine/docs/python/taskqueue/overview-push#Task_Execution
_HTTP_X_APPENGINE_QUEUENAME = 'HTTP_X_APPENGINE_QUEUENAME'

# os.environ key representing 'X-AppEngine-Cron' HTTP header,
# which should only be present for 'offline' cron requests,
# see https://developers.google.com/appengine/docs/python/config/cron#Securing_URLs_for_Cron
_HTTP_X_APPENGINE_CRON = 'HTTP_X_APPENGINE_CRON'

# TODO: see if "app.yaml" can be made into a link to the actual
# app.yaml file in the user's workspace.
_NOT_FOUND_PAGE = """
<html>
  <body>
    <h3>404 Not Found</h3>
    Your application's <code>app.yaml</code> file does not have a handler for
    the requested path: <code>%s</code><br>
    <br>
    See <a
    href="https://developers.google.com/appengine/docs/python/config/appconfig">
    https://developers.google.com/appengine/docs/python/config/appconfig</a>
  </body>
</html>
"""


def RespondWithStatus(status_code, expiration_s=0, content_type='text/plain',
                      data=None, headers=None):
  """Respond with a status code and optional text/plain data."""
  print 'Content-Type: %s' % content_type
  print 'Status: %d' % status_code
  if expiration_s:
    # TODO: Add equivalent HTTP/1.0 'Expires' header
    print 'Cache-Control: public, max-age=%s' % expiration_s
  if headers:
    for k, v in headers:
      print '{0}: {1}'.format(k, v)
  print ''
  if data is not None:
    print data,


def ServeStaticPage(tree, page):
  """Respond by serving a single static file.

  Args:
    tree: A tree object to use to retrieve files.
    page: A StaticPage object describing the file to be served.
  """
  file_path = page.file_path
  logging.info('Serving static page %s', file_path)
  file_data = tree.GetFileContents(file_path)
  if file_data is None:
    RespondWithStatus(httplib.NOT_FOUND, content_type='text/html',
                      data=_NOT_FOUND_PAGE % file_path)
    return
  if page.mime_type is not None:
    content_type = page.mime_type
  else:
    content_type, _ = mimetypes.guess_type(file_path)
  if content_type is None:
    if file_path.lower().endswith('.ico'):
      content_type = 'image/x-icon'
    else:
      content_type = 'text/plain'
  # should not raise ConfigurationError, but even that would be ok
  expiration_s = appinfo.ParseExpiration(page.expiration)
  RespondWithStatus(httplib.OK, content_type=content_type,
                    data=file_data, expiration_s=expiration_s)


def ServeScriptPage(tree, config, page, project_name):
  """Respond by invoking a python cgi script.

  Args:
    tree: A tree object to use to retrieve files.
    config: The app's config loaded from the app's app.yaml.
    page: A ScriptPage object describing the file to be served.
    project_name: The name of the project for namespace prefixing
  """
  logging.info('Serving script page %s', page.script_path)
  env = target_env.TargetEnvironment(tree, config, project_name)
  try:
    env.RunScript(page.script_path, control.LoggingHandler())
  except target_env.ScriptNotFoundError:
    RespondWithStatus(httplib.NOT_FOUND,
                      data='Error: could not find script %s' % page.script_path)


def _IsAuthorized(page, users_mod):
  # page does not require login
  if page.login == target_info.LOGIN_NONE:
    return True

  # admins are always allowed in
  # call get_current_user even though checking is_current_user_admin suffices
  if (users_mod.get_current_user() is not None and
      users_mod.is_current_user_admin()):
    return True

  # treat task queue and cron requests as admin equivalents
  # note: mimic currently does not actually provide cron support
  if (os.environ.get(_HTTP_X_APPENGINE_QUEUENAME) or
      os.environ.get(_HTTP_X_APPENGINE_CRON)):
    return True

  # login required and user is currently logged in
  if (page.login == target_info.LOGIN_REQUIRED and
      users_mod.get_current_user() is not None):
    return True

  return False


def _GetUrl(force_https=False):
  if force_https:
    scheme = 'https'
  else:
    scheme = os.environ['wsgi.url_scheme']
  url = '{0}://{1}{2}'.format(scheme, os.environ['HTTP_HOST'],
                              os.environ['PATH_INFO'])
  query = os.environ['QUERY_STRING']
  if query:
    url = '{0}?{1}'.format(url, query)
  return url


def RunTargetApp(tree, path_info, project_name, users_mod):
  """Top level handling of target application requests.

  Args:
    tree: A tree object to use to retrieve files.
    path_info: The path to be served.
    project_name: The name of the project for namespace prefixing.
    users_mod: A users module to use for authentication.
  """
  app_yaml = tree.GetFileContents('app.yaml')
  if app_yaml is None:
    RespondWithStatus(httplib.NOT_FOUND, data='Error: no app.yaml file.')
    return
  try:
    config = yaml.load(app_yaml)
  except yaml.YAMLError:
    errmsg = ('Error: app.yaml configuration is missing or invalid: {0}'
              .format(sys.exc_info()[1]))
    RespondWithStatus(httplib.NOT_FOUND, data=errmsg)
    return
  # bail if yaml.load fails to return dict due to malformed yaml input
  if not isinstance(config, dict):
    errmsg = 'Error: app.yaml configuration is missing or invalid.'
    RespondWithStatus(httplib.NOT_FOUND, data=errmsg)
    return
  page = target_info.FindPage(config, path_info)

  if not page:
    RespondWithStatus(httplib.NOT_FOUND, content_type='text/html',
                      data=_NOT_FOUND_PAGE % path_info)

  # in production redirect to https for handlers specifying 'secure: always'
  if (page.secure == target_info.SECURE_ALWAYS
      and not common.IsDevMode()
      and os.environ['wsgi.url_scheme'] != 'https'):
    https_url = _GetUrl(force_https=True)
    RespondWithStatus(httplib.FOUND, headers=[('Location', https_url)])
    return

  if not _IsAuthorized(page, users_mod):
    user = users_mod.get_current_user()
    if user:
      url = users_mod.create_logout_url(_GetUrl())
      message = ('User <b>{0}</b> is not authorized to view this page.<br>'
                 'Please <a href="{1}">logout</a> and then login as an '
                 'authorized user.'.format(user.nickname(), url))
    else:
      url = users_mod.create_login_url(_GetUrl())
      message = ('You are not authorized to view this page. '
                 'You may need to <a href="{0}">login</a>.'.format(url))
    RespondWithStatus(httplib.FORBIDDEN, data=message,
                      headers=[('Content-Type', 'text/html')])
    return
  # dispatch the page
  if isinstance(page, target_info.StaticPage):
    ServeStaticPage(tree, page)
  elif isinstance(page, target_info.ScriptPage):
    ServeScriptPage(tree, config, page, project_name)
  else:
    raise NotImplementedError('Unrecognized page {0!r}'.format(page))


def GetProjectName():
  """Returns the project name from the SERVER_NAME env var.

     For appspot.com domains, a project name is extracted from the left most
     portion of the subdomain. If no subdomain is specified, or if the project
     name cannot be determined, '' is returned. Finally, when the server name
     is 'localhost', '' is also returned.

     For custom domains, it's not possible to determine with certainty the
     subdomain vs. the default version hostname. In this case we end up using
     the left most component of the server name.

     Example mapping of server name to project name:

     Server Name                              Project Name
     -----------                              ------------
     proj1.your-app-id.appspot.com        ->  'proj1'
     proj1-dot-your-app-id.appspot.com    ->  'proj1'
     your-app-id.appspot.com              ->  ''
     www.mydomain.com                     ->  'www'
     proj2.www.mydomain.com               ->  'proj2'
     localhost                            ->  ''

  """
  # The project name is sent as a "subdomain" of the app, e.g.
  # 'project-name-dot-your-app-id.appspot.com' or
  # 'project-name.your-app-id.appspot.com'

  server_name = os.environ['SERVER_NAME']
  # use a consistent delimiter
  server_name = server_name.replace('-dot-', '.')

  if (server_name == 'localhost' or
      server_name == app_identity.get_default_version_hostname()):
    return ''

  return server_name.split('.')[0]


def RunMimic(datastore_tree_func=datastore_tree.DatastoreTree,
             users_mod=users):
  """Entry point for mimic.

  Args:
    datastore_tree_func: A callable that creates an DatastoreTree (default
        is the DatastoreTree class itself).
    users_mod: A users module to use for authentication (default is the
        AppEngine users module).
  """
  # use PATH_INFO to determine if this is a control or target request
  path_info = os.environ['PATH_INFO']

  is_control_request = path_info.startswith(common.CONTROL_PREFIX)
  if is_control_request:
    # some control requests don't require a tree, like /version_id
    requires_tree = control.ControlRequestRequiresTree(path_info)
  else:
    # requests to the target app always require a tree
    requires_tree = True

  if requires_tree:
    project_name = GetProjectName()
    tree = datastore_tree_func(project_name)
  else:
    tree = None

  if is_control_request:
    run_wsgi_app(control.MakeControlApp(tree))
  elif path_info.startswith(common.SHELL_PREFIX):
    run_wsgi_app(shell.MakeShellApp(tree, project_name))
  else:
    RunTargetApp(tree, path_info, project_name, users_mod)
