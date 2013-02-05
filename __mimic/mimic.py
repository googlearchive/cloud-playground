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
  to the files retrieved from the provided tree.

The target application may include Python code which will expect to run
in a pristine environment, so measures are taken not to invoke any sort of
WSGI framework until it is determined that the request is a control request.
"""

import httplib
import logging
import mimetypes
import os
import rfc822
import sys
import time
import urlparse


from __mimic import common
from __mimic import control
from __mimic import shell
from __mimic import target_env
from __mimic import target_info
import yaml

from google.appengine.api import app_identity
# pylint: disable-msg=g-import-not-at-top
try:
  from google.appengine.api import appinfo
except ImportError:
  # import parts of the google.appengine.api.appinfo package (extracted from
  # the local SDK by sdkapi.sh), since the appinfo package is currently
  # unavailable in the App Engine production environment
  from sdkapi import appinfo
from google.appengine.api import namespace_manager
from google.appengine.api import users
from google.appengine.ext.webapp.util import run_wsgi_app
# pylint: enable-msg=g-import-not-at-top

# os.environ key representing 'X-AppEngine-QueueName' HTTP header,
# which should only be present for 'offline' task queue requests, see
# https://developers.google.com/appengine/docs/python/taskqueue/overview-push#Task_Execution
_HTTP_X_APPENGINE_QUEUENAME = 'HTTP_X_APPENGINE_QUEUENAME'

# os.environ key representing 'X-AppEngine-Cron' HTTP header,
# which should only be present for 'offline' cron requests, see
# https://developers.google.com/appengine/docs/python/config/cron#Securing_URLs_for_Cron
_HTTP_X_APPENGINE_CRON = 'HTTP_X_APPENGINE_CRON'

# os.environ key representing 'X-AppEngine-Current-Namespace' HTTP header,
# which identifies the effective namespace when a task was created
_HTTP_X_APPENGINE_CURRENT_NAMESPACE = 'HTTP_X_APPENGINE_CURRENT_NAMESPACE'

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

# most recently seen query string project_id (dev_appserver only)
_most_recent_query_string_project_id = None


def RespondWithStatus(status_code, expiration_s=0, content_type='text/plain',
                      data=None, headers=None):
  """Respond with a status code and optional text/plain data."""
  print 'Content-Type: %s' % content_type
  print 'Status: %d' % status_code
  if expiration_s:
    print 'Expires: %s' % rfc822.formatdate(time.time() + expiration_s)
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


def ServeScriptPage(tree, config, page, namespace):
  """Respond by invoking a python cgi script.

  Args:
    tree: A tree object to use to retrieve files.
    config: The app's config loaded from the app's app.yaml.
    page: A ScriptPage object describing the file to be served.
    namespace: The datastore and memcache namespace used for metadata.
  """
  logging.info('Serving script page %s', page.script_path)
  env = target_env.TargetEnvironment(tree, config, namespace)
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


def RunTargetApp(tree, path_info, namespace, users_mod):
  """Top level handling of target application requests.

  Args:
    tree: A tree object to use to retrieve files.
    path_info: The path to be served.
    namespace: The datastore and memcache namespace used for metadata.
    users_mod: A users module to use for authentication.
  """
  app_yaml = tree.GetFileContents('app.yaml')
  if app_yaml is None:
    RespondWithStatus(httplib.NOT_FOUND, data='Error: no app.yaml file.')
    return
  try:
    config = yaml.safe_load(app_yaml)
  except yaml.YAMLError:
    errmsg = ('Error: app.yaml configuration is missing or invalid: {0}'
              .format(sys.exc_info()[1]))
    RespondWithStatus(httplib.NOT_FOUND, data=errmsg)
    return
  # bail if yaml.safe_load fails to return dict due to malformed yaml input
  if not isinstance(config, dict):
    errmsg = 'Error: app.yaml configuration is missing or invalid.'
    RespondWithStatus(httplib.NOT_FOUND, data=errmsg)
    return
  page = target_info.FindPage(config, path_info)

  if not page:
    RespondWithStatus(httplib.NOT_FOUND, content_type='text/html',
                      data=_NOT_FOUND_PAGE % path_info)
    return

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
    ServeScriptPage(tree, config, page, namespace)
  else:
    raise NotImplementedError('Unrecognized page {0!r}'.format(page))


def GetProjectIdFromServerName():
  """Returns the project id from the SERVER_NAME env var.

  For appspot.com domains, a project id is extracted from the left most
  portion of the subdomain. If no subdomain is specified, or if the project
  id cannot be determined, '' is returned. Finally, when the server name
  is 'localhost', '' is also returned.

  For custom domains, it's not possible to determine with certainty the
  subdomain vs. the default version hostname. In this case we end up using
  the left most component of the server name.

  Example mapping of server name to project id:

  Server Name                              Project Id
  -----------                              ------------
  proj1.your-app-id.appspot.com        ->  'proj1'
  proj1-dot-your-app-id.appspot.com    ->  'proj1'
  your-app-id.appspot.com              ->  None
  www.mydomain.com                     ->  'www'
  proj2.www.mydomain.com               ->  'proj2'
  localhost                            ->  None

  Returns:
    The project id or None.
  """
  # The project id is sent as a "subdomain" of the app, e.g.
  # 'project-id-dot-your-app-id.appspot.com' or
  # 'project-id.your-app-id.appspot.com'

  server_name = os.environ['SERVER_NAME']
  # use a consistent delimiter
  server_name = server_name.replace('-dot-', '.')

  if (server_name == 'localhost' or
      server_name == app_identity.get_default_version_hostname()):
    return None

  return server_name.split('.')[0]


def GetProjectIdFromDevAppserverQueryParam():
  """Returns the project id from the (or a recent) project id query param.

  In the dev_appserver, we need to support running any one of the (potentially)
  many cloud playground projects. Because subdomains would be extremely painful
  to use in the localhost environment, we extract the project id from the
  current query string, or the most recently provided query string project id.
  In production, we use subdomains, so always return None.

  Returns:
    The project id or None.
  """
  global _most_recent_query_string_project_id  # pylint: disable-msg=W0603
  if not common.IsDevMode():
    return None
  qs = os.environ.get('QUERY_STRING')
  if qs:
    params = dict(urlparse.parse_qsl(qs, strict_parsing=True))
    _most_recent_query_string_project_id = params.get(
        common.config.PROJECT_ID_QUERY_PARAM,
        _most_recent_query_string_project_id)
  return _most_recent_query_string_project_id


def GetProjectIdFromPathInfo(path_info):
  """Returns the project id from the request path."""
  m = common.config.PROJECT_ID_FROM_PATH_INFO_RE.match(path_info)
  if not m:
    return None
  return m.group(1)


def GetProjectId():
  """Returns the project id from the HTTP request.

  A number of sources for project id are tried in order. See implementation
  details.

  Returns:
    The project id or None.
  """
  # for task queues, use persisted namespace as the project id
  project_id = os.environ.get(_HTTP_X_APPENGINE_CURRENT_NAMESPACE)
  if project_id:
    return project_id
  project_id = GetProjectIdFromPathInfo(os.environ['PATH_INFO'])
  if project_id:
    return project_id
  project_id = GetProjectIdFromServerName()
  if project_id:
    return project_id
  return GetProjectIdFromDevAppserverQueryParam()


def GetNamespace():
  namespace = GetProjectId() or ''
  # throws BadValueError
  namespace_manager.validate_namespace(namespace)
  return namespace


def RunMimic(create_tree_func, users_mod=users):
  """Entry point for mimic.

  Args:
    create_tree_func: A callable that creates a common.Tree.
    users_mod: A users module to use for authentication (default is the
        AppEngine users module).
  """
  # ensures that namespace_manager_default_namespace_for_request is used
  namespace_manager.set_namespace(None)

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
    namespace = GetNamespace()
    tree = create_tree_func(namespace)
  else:
    tree = None

  if is_control_request:
    run_wsgi_app(control.MakeControlApp(tree))
  elif path_info.startswith(common.SHELL_PREFIX):
    run_wsgi_app(shell.MakeShellApp(tree, namespace))
  else:
    RunTargetApp(tree, path_info, namespace, users_mod)
