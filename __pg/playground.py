"""Module containing the playground WSGI handlers."""

import cgi
import httplib
import json
import os
import re
import urllib

import webapp2

from . import appids
from . import error
from error import Abort
from . import fixit
from . import middleware
from mimic.__mimic import common
from mimic.__mimic import mimic
from . import model
from . import settings
from . import shared
from template import templates
from . import wsgi_config

from google.appengine.api import users


_JSON_MIME_TYPE = 'application/json'

_JSON_ENCODER = json.JSONEncoder()
_JSON_ENCODER.indent = 4
_JSON_ENCODER.sort_keys = True

_DEV_APPSERVER = os.environ['SERVER_SOFTWARE'].startswith('Development/')

_DASH_DOT_DASH = '-dot-'

# must fit in front of '-dot-appid.appspot.com' and not contain '-dot-'
_VALID_PROJECT_RE = re.compile('^[a-z0-9-]{0,50}$')


def tojson(r):  # pylint:disable-msg=invalid-name
  """Converts a python object to JSON."""
  return _JSON_ENCODER.encode(r)


class PlaygroundHandler(webapp2.RequestHandler):
  """Convenience request handler with playground specific functionality."""

  @webapp2.cached_property
  def project_id(self):  # pylint:disable-msg=invalid-name
    return mimic.GetProjectId(self.request.environ, False)

  @webapp2.cached_property
  def project(self):  # pylint:disable-msg=invalid-name
    return self.request.environ['playground.project']

  @webapp2.cached_property
  def user(self):  # pylint:disable-msg=invalid-name
    return self.request.environ['playground.user']

  @webapp2.cached_property
  def tree(self):  # pylint:disable-msg=invalid-name
    # TODO: instantiate tree elsewhere
    return common.config.CREATE_TREE_FUNC(str(self.project.key.id()))

  # pylint:disable-msg=invalid-name
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
    if project.owner == settings.MANUAL_PROJECT_TEMPLATE_OWNER:
      orderby = '4-{}-{}'.format(project.project_name,
                                    project.updated.isoformat())
    elif project.owner == settings.PUBLIC_PROJECT_TEMPLATE_OWNER:
      orderby = '1-{}'.format(project.orderby or '')
    else:
      orderby = '2-{}-{}'.format(project.owner, project.updated.isoformat())

    return {
        # cast to str since JavaScript doesn't support long
        'key': str(project.key.id()),
        'owner': project.owner,
        'name': project.project_name,
        'description': project.project_description,
        'open_files': project.open_files,
        'template_url': project.template_url,
        'html_url': project.html_url,
        'run_url': self._MakeMimicUrl(project, '/'),
        'control_url': self._MakeMimicUrl(project, '/_ah/mimic/log',
                                          {'mode': 'postMessage',
                                           'debug': 'false'}),
        'in_progress_task_name': project.in_progress_task_name,
        'orderby': orderby,
        'writers': project.writers,
        'access_key': project.access_key,
        'expiration_seconds': project.expiration_seconds,
        'writable': self.user.key.id() in project.writers,
    }

  def _MakeMimicUrl(self, project, path, params=None):
    """Build a mimic url."""
    if params is None:
      params = {}
    project_id = urllib.quote_plus(str(project.key.id()))
    path = path.lstrip('/')
    if common.IsDevMode():
      url = ('{0}://{1}/{2}'
             .format(self.request.scheme,
                     settings.MIMIC_HOST,
                     path))
      params.update({
          common.config.PROJECT_ID_QUERY_PARAM: project_id,
      })
    else:
      url = ('{0}://{1}{2}{3}/{4}'
             .format(self.request.scheme,
                     project_id,
                     _DASH_DOT_DASH,
                     settings.MIMIC_HOST,
                     path))
    params.update({
        settings.ACCESS_KEY_SET_COOKIE_PARAM_NAME: project.access_key,
    })
    if params:
      url = '{}?{}'.format(url, urllib.urlencode(params))
    return url

  def PerformAccessCheck(self):
    """Perform authorization checks.

    Subclasses must provide a suitable implementation.

    Raises:
      error.PlaygroundError if autorization check fails
    """
    raise NotImplementedError()

  def dispatch(self):  # pylint:disable-msg=invalid-name
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
      return appids.PLAYGROUND_APP_ID
    else:
      return appids.MIMIC_APP_ID


class DatastoreRedirect(RedirectHandler):
  """Handler for redirecting to the datastore admin page."""

  def PerformAccessCheck(self):
    pass

  def get(self, namespace):  # pylint:disable-msg=invalid-name
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

  def get(self, namespace):  # pylint:disable-msg=invalid-name
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

  def get(self):  # pylint:disable-msg=invalid-name
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

  def post(self):  # pylint:disable-msg=invalid-name
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
    if not shared.HasProjectReadAccess(self.request.environ):
      Abort(httplib.UNAUTHORIZED, 'no project read access')

  def get(self):  # pylint:disable-msg=invalid-name
    r = self.DictOfProject(self.project)
    self.response.headers['Content-Type'] = _JSON_MIME_TYPE
    self.response.write(tojson(r))


class GetProjects(PlaygroundHandler):
  """Handler which gets the user's projects and template projects."""

  def PerformAccessCheck(self):
    pass

  def get(self):  # pylint:disable-msg=invalid-name
    user_projects = model.GetProjects(self.user)
    template_projects = model.GetPublicTemplateProjects()
    projects = user_projects + template_projects
    r = [self.DictOfProject(p) for p in projects]
    self.response.headers['Content-Type'] = _JSON_MIME_TYPE
    self.response.write(tojson(r))


class Login(PlaygroundHandler):
  """Login handler."""

  def PerformAccessCheck(self):
    pass

  def get(self):  # pylint:disable-msg=invalid-name
    """Handles HTTP GET requests."""
    self.redirect(users.create_login_url('/playground'))


class Logout(PlaygroundHandler):
  """Logout handler."""

  def PerformAccessCheck(self):
    pass

  def get(self):  # pylint:disable-msg=invalid-name
    """Handles HTTP GET requests."""
    self.redirect(users.create_logout_url('/playground'))


class CopyProject(PlaygroundHandler):
  """Request handler for copying projects."""

  def PerformAccessCheck(self):
    if not shared.HasProjectReadAccess(self.request.environ):
      Abort(httplib.UNAUTHORIZED, 'no project read access')

  def post(self):  # pylint:disable-msg=invalid-name
    """Handles HTTP POST requests."""
    tp = self.request.environ['playground.project']
    if not tp or tp.in_progress_task_name:
      Abort(httplib.REQUEST_TIMEOUT,
            'Sorry. Requested template is not yet available. '
            'Please try again in 30 seconds.')
    expiration_seconds = self.request.data.get('expiration_seconds')
    project = model.CopyProject(self.user, tp, expiration_seconds)
    r = self.DictOfProject(project)
    self.response.headers['Content-Type'] = _JSON_MIME_TYPE
    self.response.write(tojson(r))


class RecreateTemplateProject(PlaygroundHandler):
  """Request handler for recreating template projects."""

  def PerformAccessCheck(self):
    shared.AssertIsAdmin()

  def post(self):  # pylint:disable-msg=invalid-name
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
    model.CreateRepoAsync(owner=model.GetOrCreateUser(repo.owner),
                          repo_url=repo.key.id(),
                          html_url=repo.html_url,
                          name=repo.name,
                          description=repo.description,
                          open_files=repo.open_files)


class NewProjectFromTemplateUrl(PlaygroundHandler):
  """Request handler for creating projects from template URLs."""

  def PerformAccessCheck(self):
    pass

  def post(self):  # pylint:disable-msg=invalid-name
    """Handles HTTP POST requests."""
    repo_url = self.request.data.get('repo_url')
    if not repo_url:
      Abort(httplib.BAD_REQUEST, 'repo_url required')
    repo = model.GetRepo(repo_url)
    if not repo:
      html_url = name = description = repo_url
      repo = model.CreateRepoAsync(owner=model.GetManualTemplateOwner(),
                                   repo_url=repo_url,
                                   html_url=html_url,
                                   name=name,
                                   description=description,
                                   open_files=[])
    template_project = repo.project.get()
    if not template_project or template_project.in_progress_task_name:
      Abort(httplib.REQUEST_TIMEOUT,
            'Sorry. Requested template is not yet available. '
            'Please try again in 30 seconds.')
    expiration_seconds = self.request.data.get('expiration_seconds')
    project = model.CopyProject(self.user, template_project, expiration_seconds)
    r = self.DictOfProject(project)
    self.response.headers['Content-Type'] = _JSON_MIME_TYPE
    self.response.write(tojson(r))


class CreateTemplateProjectByUrl(PlaygroundHandler):
  """Request handler for (re)creating template projects."""

  def PerformAccessCheck(self):
    pass

  def post(self):  # pylint:disable-msg=invalid-name
    """Handles HTTP POST requests."""
    repo_url = self.request.data.get('repo_url')
    if not repo_url:
      Abort(httplib.BAD_REQUEST, 'repo_url required')
    repo = model.GetRepo(repo_url)
    if not repo:
      html_url = name = description = repo_url
      repo = model.CreateRepoAsync(owner=model.GetManualTemplateOwner(),
                                   repo_url=repo_url,
                                   html_url=html_url,
                                   name=name,
                                   description=description,
                                   open_files=[])
    project = repo.project.get()
    if not project or project.in_progress_task_name:
      Abort(httplib.REQUEST_TIMEOUT,
            'Sorry. Requested template is not yet available. '
            'Please try again in 30 seconds.')
    r = self.DictOfProject(project)
    self.response.headers['Content-Type'] = _JSON_MIME_TYPE
    self.response.write(tojson(r))


class DeleteProject(PlaygroundHandler):
  """Handler for deleting a project."""

  def PerformAccessCheck(self):
    if not shared.HasProjectWriteAccess(self.request.environ):
      Abort(httplib.UNAUTHORIZED, 'no project write access')

  def post(self):  # pylint:disable-msg=invalid-name
    model.DeleteProject(self.project)


class RenameProject(PlaygroundHandler):
  """Handler for renaming a project."""

  def PerformAccessCheck(self):
    if not shared.HasProjectWriteAccess(self.request.environ):
      Abort(httplib.UNAUTHORIZED, 'no project write access')

  def post(self):  # pylint:disable-msg=invalid-name
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
    if not shared.HasProjectWriteAccess(self.request.environ):
      Abort(httplib.UNAUTHORIZED, 'no project write access')

  def post(self):  # pylint:disable-msg=invalid-name
    project = model.ResetProject(self.project_id, self.tree)
    r = self.DictOfProject(project)
    self.response.headers['Content-Type'] = _JSON_MIME_TYPE
    self.response.write(tojson(r))


class TouchProject(PlaygroundHandler):
  """Handler for updating the project last access timestamp."""

  def PerformAccessCheck(self):
    if not shared.HasProjectWriteAccess(self.request.environ):
      Abort(httplib.UNAUTHORIZED, 'no project write access')

  def post(self):  # pylint:disable-msg=invalid-name
    project = model.TouchProject(self.project_id)
    r = self.DictOfProject(project)
    self.response.headers['Content-Type'] = _JSON_MIME_TYPE
    self.response.write(tojson(r))


class Fixit(PlaygroundHandler):
  """Admin only handler for initiating data cleanup operations."""

  def PerformAccessCheck(self):
    shared.AssertIsAdmin()

  def get(self):  # pylint:disable-msg=invalid-name
    fixit.Begin()
    self.response.write('Fixit begun')


class Nuke(PlaygroundHandler):
  """Admin only handler for reseting global data."""

  def PerformAccessCheck(self):
    shared.AssertIsAdmin()

  def post(self):  # pylint:disable-msg=invalid-name
    if not users.is_current_user_admin():
      shared.e('You must be an admin for this app')
    model.DeleteReposAndTemplateProjects()
    # force reinitialization
    templates.GetRepoCollections()
    self.redirect('/playground')


class CheckExpiration(webapp2.RequestHandler):
  """Checks to see if project should be expired."""

  def post(self):  # pylint:disable-msg=invalid-name
    project = self.request.environ.get('playground.project')
    model.CheckExpiration(project)

app = webapp2.WSGIApplication([
    # config actions
    ('/playground/getconfig', GetConfig),

    # project actions
    ('/playground/recreate_template_project', RecreateTemplateProject),
    ('/playground/create_template_project_by_url', CreateTemplateProjectByUrl),
    ('/playground/new_project_from_template_url', NewProjectFromTemplateUrl),
    ('/playground/getprojects', GetProjects),
    ('/playground/p/.*/copy', CopyProject),
    ('/playground/p/.*/retrieve', RetrieveProject),
    ('/playground/p/.*/delete', DeleteProject),
    ('/playground/p/.*/rename', RenameProject),
    ('/playground/p/.*/touch', TouchProject),
    ('/playground/p/.*/reset', ResetProject),

    # admin tools
    ('/playground/nuke', Nuke),
    ('/playground/fixit', Fixit),
    ('/playground/oauth2_admin', OAuth2Admin),

    # /playground
    ('/playground/login', Login),
    ('/playground/logout', Logout),
    ('/playground/datastore/(.*)', DatastoreRedirect),
    ('/playground/memcache/(.*)', MemcacheRedirect),
], debug=settings.DEBUG)
app = middleware.Session(app, wsgi_config.WSGI_CONFIG)
app = middleware.ProjectFilter(app)
app = middleware.ErrorHandler(app, debug=settings.DEBUG)

internal_app = webapp2.WSGIApplication([
    ('/playground/p/.*/check_expiration', CheckExpiration)
], debug=settings.DEBUG)
internal_app = middleware.ProjectFilter(internal_app)
