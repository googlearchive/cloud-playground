"""Module containing the playground WSGI handlers."""

import cgi
import httplib
import json
import logging
import os
import re
import StringIO
import urllib
import zipfile

import webapp2
from webapp2_extras import sessions

import error
from error import *
import fixit
import middleware
from mimic import mimic_wsgi
from mimic.__mimic import common
from mimic.__mimic import mimic
import model
import secret
import settings
import shared

from template import templates

from google.appengine.api import namespace_manager
from google.appengine.api import users


DEBUG = True

_JSON_MIME_TYPE = 'application/json'

_JSON_ENCODER = json.JSONEncoder()
_JSON_ENCODER.indent = 4
_JSON_ENCODER.sort_keys = True

_DEV_APPSERVER = os.environ['SERVER_SOFTWARE'].startswith('Development/')

_DASH_DOT_DASH = '-dot-'

# must fit in front of '-dot-appid.appspot.com' and not contain '-dot-'
_VALID_PROJECT_RE = re.compile('^[a-z0-9-]{0,50}$')


def tojson(r):
  """Converts a python object to JSON."""
  return _JSON_ENCODER.encode(r)


class Warmup(webapp2.RequestHandler):
  """Handler for warmup/start requests"""

  def get(self):
    templates.GetRepoCollections()


class PlaygroundHandler(webapp2.RequestHandler):
  """Convenience request handler with playground specific functionality."""

  @webapp2.cached_property
  def project_id(self):
    return mimic.GetProjectId(self.request.environ, False)

  @webapp2.cached_property
  def project(self):
    return self.request.environ['playground.project']

  @webapp2.cached_property
  def user(self):
    return self.request.environ['playground.user']

  @webapp2.cached_property
  def tree(self):
    # TODO: instantiate tree elsewhere
    return common.config.CREATE_TREE_FUNC(str(self.project.key.id()))

  def handle_exception(self, exception, debug_mode):
    """Called if this handler throws an exception during execution.

    Args:
      exception: the exception that was thrown
      debug_mode: True if the web application is running in debug mode
    """
    status, headers, body = error.MakeErrorResponse(exception, debug_mode)
    self.response.clear()
    self.error(status)
    self.response.headers.extend(headers)
    self.response.write('{}'.format(cgi.escape(body, quote=True)))

  def DictOfProject(self, project):
    return {
        # cast to str since JavaScript doesn't support long
        'key': str(project.key.id()),
        'name': project.project_name,
        'description': project.project_description,
        'open_files': project.open_files,
        'template_url': project.template_url,
        'html_url': project.html_url,
        'run_url': self._GetPlaygroundRunUrl(project),
        'in_progress_task_name': project.in_progress_task_name,
        'orderby': project.orderby,
        'writers': project.writers,
        'access_key': project.access_key,
    }

  def _GetPlaygroundRunUrl(self, project):
    """Determine the playground run url."""
    if common.IsDevMode():
      return ('{0}://{1}/?{2}={3}&{4}={5}'
              .format(self.request.scheme,
                      settings.EXEC_CODE_HOST,
                      common.config.PROJECT_ID_QUERY_PARAM,
                      urllib.quote_plus(str(project.key.id())),
                      settings.ACCESS_KEY_SET_COOKIE_PARAM_NAME,
                      project.access_key))
    else:
      return ('{0}://{1}{2}{3}/?{4}={5}'
              .format(self.request.scheme,
                      urllib.quote_plus(str(project.key.id())),
                      _DASH_DOT_DASH,
                      settings.EXEC_CODE_HOST,
                      settings.ACCESS_KEY_SET_COOKIE_PARAM_NAME,
                      project.access_key))

  def PerformAccessCheck(self):
    """Perform authorization checks.

    Subclasses must provide a suitable implementation.

    Raises:
      error.PlaygroundError if autorization check fails
    """
    raise NotImplementedError()


  def dispatch(self):
    """WSGI request dispatch with automatic JSON parsing."""
    try:
      if not shared.ThisIsPlaygroundApp():
        Abort(httplib.FORBIDDEN,
              'playground handlers are not available in this app id')
      self.PerformAccessCheck()
    except error.PlaygroundError, e:
      # Manually dispatch to handle_exception
      self.handle_exception(e, self.app.debug)
      return

    content_type = self.request.headers.get('Content-Type')
    if content_type and content_type.split(';')[0] == 'application/json':
      self.request.data = json.loads(self.request.body)
    # Exceptions in super.dispatch are automatically routed to handle_exception
    super(PlaygroundHandler, self).dispatch()


class RedirectHandler(PlaygroundHandler):
  """Handler for redirecting an admin page."""

  def _GetAppId(self, namespace):
    if namespace == settings.PLAYGROUND_NAMESPACE:
      return settings.PLAYGROUND_APP_ID
    else:
      return settings.EXEC_CODE_APP_ID


class DatastoreRedirect(RedirectHandler):
  """Handler for redirecting to the datastore admin page."""

  def PerformAccessCheck(self):
    pass

  def get(self, namespace):
    if _DEV_APPSERVER:
      url = '//localhost:8000/datastore?namespace={0}'.format(namespace)
    else:
      url = ('https://appengine.google.com/datastore/explorer'
             '?&app_id={0}&namespace={1}'
             .format(self._GetAppId(namespace), namespace))
    self.redirect(url)


class MemcacheRedirect(RedirectHandler):
  """Handler for redirecting to the memcache admin page."""

  def PerformAccessCheck(self):
    pass

  def get(self, namespace):
    if _DEV_APPSERVER:
      url = '//localhost:8000/memcache?namespace={0}'.format(namespace)
    else:
      url = ('https://appengine.google.com/memcache'
             '?&app_id={0}&namespace={1}'
             .format(self._GetAppId(namespace), namespace))
    self.redirect(url)


class GetConfig(PlaygroundHandler):
  """Handler for retrieving config data."""

  def PerformAccessCheck(self):
    pass

  def get(self):
    """Handles HTTP GET requests."""
    r = {
        'PLAYGROUND_USER_CONTENT_HOST': settings.PLAYGROUND_USER_CONTENT_HOST,
        'git_playground_url': 'http://code.google.com/p/cloud-playground/',
        'playground_namespace': settings.PLAYGROUND_NAMESPACE,
        'email': self.user.key.id(),
        'is_logged_in': bool(users.get_current_user()),
        'is_admin': bool(users.is_current_user_admin()),
        'is_devappserver': bool(_DEV_APPSERVER),
    }
    self.response.headers['Content-Type'] = _JSON_MIME_TYPE
    self.response.write(tojson(r))


class OAuth2Admin(PlaygroundHandler):
  """Admin only hander for editing OAuth2 credentials."""

  def PerformAccessCheck(self):
    shared.AssertIsAdmin()

  def post(self):
    """Handles HTTP POST requests."""
    if not users.is_current_user_admin():
      self.response.set_status(httplib.UNAUTHORIZED)
      return
    data = json.loads(self.request.body)
    key = data['key']
    url = data['url']
    client_id = data.get('client_id')
    client_secret = data.get('client_secret')
    if client_id and client_secret:
      credential = model.SetOAuth2Credential(key, client_id, client_secret)
    else:
      credential = model.GetOAuth2Credential(key) or model.OAuth2Credential()
    r = {
        'key': key,
        'url': url,
        'client_id': credential.client_id,
        'client_secret': credential.client_secret,
    }
    self.response.headers['Content-Type'] = _JSON_MIME_TYPE
    self.response.write(tojson(r))


class RetrieveProject(PlaygroundHandler):
  """Handler to retrieve project metadata."""

  def PerformAccessCheck(self):
    shared.AssertHasProjectReadAccess(self.request.environ)

  def get(self):
    r = self.DictOfProject(self.project)
    self.response.headers['Content-Type'] = _JSON_MIME_TYPE
    self.response.write(tojson(r))


class GetProjects(PlaygroundHandler):
  """Handler which gets the user's projects."""

  def PerformAccessCheck(self):
    pass

  def get(self):
    r = [self.DictOfProject(p) for p in model.GetProjects(self.user)]
    self.response.headers['Content-Type'] = _JSON_MIME_TYPE
    self.response.write(tojson(r))


class GetTemplateProjects(PlaygroundHandler):
  """Handler which retrieves a lsit of projects."""

  def PerformAccessCheck(self):
    pass

  def get(self):
    by_project_name = lambda p: p.project_name
    r = [self.DictOfProject(p)
         for p in sorted(model.GetTemplateProjects(), key=by_project_name)]
    self.response.headers['Content-Type'] = _JSON_MIME_TYPE
    self.response.write(tojson(r))


class Login(PlaygroundHandler):
  """Login handler."""

  def PerformAccessCheck(self):
    pass

  def get(self):
    """Handles HTTP GET requests."""
    self.redirect(users.create_login_url('/playground'))


class Logout(PlaygroundHandler):
  """Logout handler."""

  def PerformAccessCheck(self):
    pass

  def get(self):
    """Handles HTTP GET requests."""
    self.redirect(users.create_logout_url('/playground'))


class CopyProject(PlaygroundHandler):
  """Request handler for copying projects."""

  def PerformAccessCheck(self):
    shared.AssertHasProjectReadAccess(self.request.environ)

  def post(self):
    """Handles HTTP POST requests."""
    tp = self.request.environ['playground.project']
    if not tp or tp.in_progress_task_name:
      Abort(httplib.REQUEST_TIMEOUT, 'Requested template is not yet available. '
                                     'Please try again in 30  seconds.')
    project = model.CopyProject(self.user, tp)
    r = self.DictOfProject(project)
    self.response.headers['Content-Type'] = _JSON_MIME_TYPE
    self.response.write(tojson(r))


class RecreateTemplateProject(PlaygroundHandler):
  """Request handler for recreating template projects."""

  def PerformAccessCheck(self):
    shared.AssertIsAdmin()

  def post(self):
    """Handles HTTP POST requests."""
    if not users.is_current_user_admin():
      self.response.set_status(httplib.UNAUTHORIZED)
      return
    project_id = self.request.data['project_id']
    if not project_id:
      Abort(httplib.BAD_REQUEST, 'project_id required')
    project = model.GetProject(project_id)
    if not project:
      Abort(httplib.NOT_FOUND,
            'failed to retrieve project {}'.format(project_id))
    repo_url = project.template_url
    repo = model.GetRepo(repo_url)
    model.CreateRepoAsync(repo.key.id(), repo.html_url, repo.name,
                          repo.description, repo.open_files)


class CreateTemplateProjectByUrl(PlaygroundHandler):
  """Request handler for (re)creating template projects."""

  def PerformAccessCheck(self):
    pass

  def post(self):
    """Handles HTTP POST requests."""
    repo_url = self.request.data.get('repo_url')
    if not repo_url:
      Abort(httplib.BAD_REQUEST, 'repo_id required')
    repo = model.GetRepo(repo_url)
    if not repo:
      html_url = name = description = repo_url
      repo = model.CreateRepoAsync(repo_url=repo_url, html_url=html_url,
                                   name=name, description=description,
                                   open_files=[])
    project = repo.project.get()
    if not project or project.in_progress_task_name:
      Abort(httplib.REQUEST_TIMEOUT, 'Requested template is not yet available. '
                                     'Please try again in 30  seconds.')
    r = self.DictOfProject(project)
    self.response.headers['Content-Type'] = _JSON_MIME_TYPE
    self.response.write(tojson(r))


class DeleteProject(PlaygroundHandler):
  """Handler for deleting a project."""

  def PerformAccessCheck(self):
    shared.AssertHasProjectWriteAccess(self.request.environ)

  def post(self):
    model.DeleteProject(self.user, tree=self.tree, project_id=self.project_id)


class RenameProject(PlaygroundHandler):
  """Handler for renaming a project."""

  def PerformAccessCheck(self):
    shared.AssertHasProjectWriteAccess(self.request.environ)

  def post(self):
    data = json.loads(self.request.body)
    newname = data.get('newname')
    assert newname
    project = model.RenameProject(self.project_id, newname)
    r = self.DictOfProject(project)
    self.response.headers['Content-Type'] = _JSON_MIME_TYPE
    self.response.write(tojson(r))


class ResetProject(PlaygroundHandler):
  """Handler to reset a project to the template state."""

  def PerformAccessCheck(self):
    shared.AssertHasProjectWriteAccess(self.request.environ)

  def post(self):
    project = model.ResetProject(self.project_id, self.tree)
    r = self.DictOfProject(project)
    self.response.headers['Content-Type'] = _JSON_MIME_TYPE
    self.response.write(tojson(r))


class DownloadProject(PlaygroundHandler):
  """Handler for downloading project source code."""

  def PerformAccessCheck(self):
    shared.AssertHasProjectReadAccess(self.request.environ)

  def get(self):
    """Handles HTTP GET requests."""
    project_data = model.DownloadProject(self.project_id, self.tree)
    buf = StringIO.StringIO()
    zf = zipfile.ZipFile(buf, mode='w', compression=zipfile.ZIP_DEFLATED)
    for project_file in project_data['files']:
      zf.writestr(project_file['path'], project_file['content'])
    zf.close()

    filename = '{}.zip'.format(project_data['project_name'])
    content_disposition = 'attachment; filename="{}"'.format(filename)

    self.response.headers['Content-Disposition'] = content_disposition
    self.response.headers['Content-Type'] = 'application/zip'
    self.response.write(buf.getvalue())


class TouchProject(PlaygroundHandler):
  """Handler for updating the project last access timestamp."""

  def PerformAccessCheck(self):
    shared.AssertHasProjectWriteAccess(self.request.environ)

  def post(self):
    project = model.TouchProject(self.project_id)
    r = self.DictOfProject(project)
    self.response.headers['Content-Type'] = _JSON_MIME_TYPE
    self.response.write(tojson(r))


class Fixit(PlaygroundHandler):
  """Admin only handler for initiating data cleanup operations."""

  def PerformAccessCheck(self):
    shared.AssertIsAdmin()

  def get(self):
    fixit.Begin()
    self.response.write('Fixit begun')


class Nuke(PlaygroundHandler):
  """Admin only handler for reseting global data."""

  def PerformAccessCheck(self):
    shared.AssertIsAdmin()

  def post(self):
    if not users.is_current_user_admin():
      shared.e('You must be an admin for this app')
    model.DeleteReposAndTemplateProjects()
    # force reinitialization
    templates.GetRepoCollections()
    self.redirect('/playground')


config = {
    'webapp2_extras.sessions': {
        'secret_key': secret.GetSecret('webapp2_extras.sessions', entropy=128),
        'cookie_args': settings.SESSION_COOKIE_ARGS,
    }
}

app = webapp2.WSGIApplication([
    # config actions
    ('/playground/getconfig', GetConfig),

    # project actions
    ('/playground/recreate_template_project', RecreateTemplateProject),
    ('/playground/create_template_project_by_url', CreateTemplateProjectByUrl),
    ('/playground/gettemplateprojects', GetTemplateProjects),
    ('/playground/getprojects', GetProjects),
    ('/playground/p/.*/copy', CopyProject),
    ('/playground/p/.*/retrieve', RetrieveProject),
    ('/playground/p/.*/delete', DeleteProject),
    ('/playground/p/.*/rename', RenameProject),
    ('/playground/p/.*/touch', TouchProject),
    ('/playground/p/.*/reset', ResetProject),
    ('/playground/p/.*/download', DownloadProject),

    # admin tools
    ('/playground/nuke', Nuke),
    ('/playground/fixit', Fixit),
    ('/playground/oauth2_admin', OAuth2Admin),

    # /playground
    ('/playground/login', Login),
    ('/playground/logout', Logout),
    ('/playground/datastore/(.*)', DatastoreRedirect),
    ('/playground/memcache/(.*)', MemcacheRedirect),

    # warmup requests
    ('/_ah/warmup', Warmup),

    # backends in the dev_appserver
    ('/_ah/start', Warmup),
], debug=DEBUG)
app = middleware.Session(app, config)
app = middleware.ErrorHandler(app, debug=DEBUG)

mimic_intercept_app = mimic_wsgi.Mimic
mimic_intercept_app = middleware.MimicControlAccessFilter(mimic_intercept_app)
if shared.ThisIsPlaygroundApp():
  mimic_intercept_app = middleware.Session(mimic_intercept_app, config)
else:
  mimic_intercept_app = middleware.AccessKeyCookieFilter(mimic_intercept_app)
mimic_intercept_app = middleware.Redirector(mimic_intercept_app)
mimic_intercept_app = middleware.ErrorHandler(mimic_intercept_app, debug=DEBUG)
