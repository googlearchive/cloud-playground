"""Module containing the playground WSGI handlers."""

import cgi
import httplib
import json
import logging
import os
import re
import urllib

import webapp2
from webapp2_extras import security
from webapp2_extras import sessions

from __mimic import common
from __mimic import mimic

import error
import model
import secret
import settings
import shared

from google.appengine.api import app_identity
from google.appengine.api import namespace_manager
from google.appengine.api import users
from google.appengine.ext import ndb


_JSON_MIME_TYPE = 'application/json'

_JSON_ENCODER = json.JSONEncoder()
_JSON_ENCODER.indent = 4
_JSON_ENCODER.sort_keys = True

_DEV_APPSERVER = os.environ['SERVER_SOFTWARE'].startswith('Development/')

_DASH_DOT_DASH = '-dot-'

# RFC1113 formatted 'Expires' to prevent HTTP/1.0 caching
_LONG_AGO = 'Mon, 01 Jan 1990 00:00:00 GMT'

# HTTP methods which do not affect state
_HTTP_READ_METHODS = ('GET', 'OPTIONS')

# must fit in front of '-dot-appid.appspot.com' and not contain '-dot-'
_VALID_PROJECT_RE = re.compile('^[a-z0-9-]{0,50}$')

# AngularJS XSRF Cookie, see http://docs.angularjs.org/api/ng.$http
_XSRF_TOKEN_COOKIE = 'XSRF-TOKEN'

# AngularJS XSRF HTTP Header, see http://docs.angularjs.org/api/ng.$http
_XSRF_TOKEN_HEADER = 'X-XSRF-TOKEN'

_ANON_USER_KEY = u'anon_user_key'


def tojson(r):
  return _JSON_ENCODER.encode(r)


# From http://webapp-improved.appspot.com/guide/extras.html
class SessionHandler(webapp2.RequestHandler):
  """Convenience request handler for dealing with sessions."""

  def _AdoptAnonymousProjects(self, dest_user_key, source_user_key):
    model.AdoptProjects(dest_user_key, source_user_key)

  def get_user_key(self):
    """Returns the email from logged in user or the session user key."""
    user = users.get_current_user()
    anon_user_key = self.session.get(_ANON_USER_KEY)
    if user and anon_user_key:
      self._AdoptAnonymousProjects(user.email(), anon_user_key)
      self.session.pop(_ANON_USER_KEY)
    if user:
      return user.email()
    if not anon_user_key:
      suffix = security.generate_random_string(
          length=10,
          pool=security.LOWERCASE_ALPHANUMERIC)
      anon_user_key = 'user_{0}'.format(suffix)
      self.session[_ANON_USER_KEY] = anon_user_key
    return anon_user_key

  def _PerformCsrfRequestValidation(self):
    session_xsrf = self.session['xsrf']
    client_xsrf = self.request.headers.get(_XSRF_TOKEN_HEADER)
    if not client_xsrf:
      raise error.PlaygroundError('Missing client XSRF token. '
                                  'Clear your cookies and refresh the page.')
    if client_xsrf != session_xsrf:
      # do not log tokens in production
      if common.IsDevMode():
        logging.error('Client XSRF token={0!r}, session XSRF token={1!r}'
                      .format(client_xsrf, session_xsrf))
      raise error.PlaygroundError('Client XSRF token does not match session '
                                  'XSRF token. Clear your cookies and refresh '
                                  'the page.')

  def PerformValidation(self):
    """To be overriden by subclasses."""
    if self.request.method not in _HTTP_READ_METHODS:
      self._PerformCsrfRequestValidation()

  def dispatch(self):
    """WSGI request dispatch."""
    # Get a session store for this request.
    self.session_store = sessions.get_store(request=self.request)
    # Ensure valid session is present (including GET requests)
    _ = self.session
    try:
      self.user = model.GetOrCreateUser(self.get_user_key())
      self.PerformValidation()
    except error.PlaygroundError, e:
      # Manually dispatch to handle_exception
      self.handle_exception(e, self.app.debug)
      return

    try:
      # Exceptions during dispatch automatically handled by handle_exception
      super(SessionHandler, self).dispatch()
      self.response.headers['Expires'] = _LONG_AGO
    finally:
      # Save all sessions.
      self.session_store.save_sessions(self.response)

  @webapp2.cached_property
  def session(self):
    """Lazily create and return a valid session."""
    # Returns a session using the default cookie key.
    session = self.session_store.get_session()
    if not session:
      # initialize the session
      session['xsrf'] = security.generate_random_string(entropy=128)
      self.response.set_cookie(_XSRF_TOKEN_COOKIE, session['xsrf'])
    return session


class PlaygroundHandler(SessionHandler):
  """Convenice request handler with playground specific functionality."""

  @webapp2.cached_property
  def project_id(self):
    return mimic.GetProjectIdFromPathInfo(self.request.path_info)

  @webapp2.cached_property
  def project(self):
    if not self.project_id:
      return None
    return model.GetProject(self.project_id)

  @webapp2.cached_property
  def tree(self):
    if not self.project:
      raise Exception('Project {0} does not exist'.format(self.project_id))
    namespace = str(self.project_id)
    # TODO: instantiate tree elsewhere
    assert namespace_manager.get_namespace() == namespace, (
        'namespace_manager.get_namespace()={0!r} != namespace={1!r}'
        .format(namespace_manager.get_namespace(), namespace))
    return common.config.CREATE_TREE_FUNC(namespace)

  def _PerformWriteAccessCheck(self):
    user_key = self.user.key.id()
    if not user_key:
      shared.e('FIX ME: no user')
    if not self.project:
      # TODO: better approach which allows the creation of new projects
      return
    if user_key not in self.project.writers:
      raise error.PlaygroundError('You are not authorized to edit this project')

  def PerformValidation(self):
    super(PlaygroundHandler, self).PerformValidation()
    if not shared.ThisIsPlaygroundApp():
      raise error.PlaygroundError('Cloud Playground user interface not '
                                  'implemented here.')
    if self.request.method not in _HTTP_READ_METHODS:
      self._PerformWriteAccessCheck()

  def handle_playground_error(self, exception):
    """Called if this handled throws a PlaygroundError.

    Args:
      exception: the exception that was thrown
    """
    self.error(500)
    logging.exception(exception)
    self.response.clear()
    self.response.headers['Content-Type'] = 'text/plain'
    self.response.headers['X-Cloud-Playground-Error'] = 'True'
    self.response.out.write('%s' % (cgi.escape(exception.message, quote=True)))

  def handle_exception(self, exception, debug_mode):
    """Called if this handler throws an exception during execution.

    Args:
      exception: the exception that was thrown
      debug_mode: True if the web application is running in debug mode
    """
    if isinstance(exception, error.PlaygroundError):
      self.handle_playground_error(exception)
    else:
      super(PlaygroundHandler, self).handle_exception(exception, debug_mode)

  def DictOfProject(self, project):
    return {
        'key': project.key.id(),
        'name': project.project_name,
        'description': project.project_description,
        'orderby': project.orderby,
        'run_url': self._GetPlaygroundRunUrl(project.key.id()),
    }


  def _GetPlaygroundRunUrl(self, project_id):
    """Determine the playground run url."""
    assert project_id
    if common.IsDevMode():
      return '{0}://{1}/?{2}={3}'.format(self.request.scheme,
                                         settings.EXEC_CODE_HOST,
                                         common.config.PROJECT_ID_QUERY_PARAM,
                                         urllib.quote_plus(str(project_id)))
    else:
      return '{0}://{1}{2}{3}/'.format(self.request.scheme,
                                       urllib.quote_plus(str(project_id)),
                                       _DASH_DOT_DASH,
                                       settings.EXEC_CODE_HOST)

  def dispatch(self):
    """WSGI request dispatch with automatic JSON parsing."""
    content_type = self.request.headers.get('Content-Type')
    if content_type and content_type.split(';')[0] == 'application/json':
      self.request.data = json.loads(self.request.body)
    super(PlaygroundHandler, self).dispatch()


class RedirectHandler(PlaygroundHandler):

  def _GetAppId(self, namespace):
      if namespace == settings.PLAYGROUND_NAMESPACE:
        app_id = settings.PLAYGROUND_APP_ID
      else:
        app_id = settings.EXEC_CODE_APP_ID


class DatastoreRedirect(RedirectHandler):

  def get(self, namespace):
    if _DEV_APPSERVER:
      url = '/_ah/admin/datastore?namespace={0}'.format(namespace)
    else:
      url = ('https://appengine.google.com/datastore/explorer'
             '?&app_id={0}&namespace={1}'
             .format(self._GetAppId(namepsace), namespace))
    self.redirect(url)


class MemcacheRedirect(RedirectHandler):

  def get(self, namespace):
    if _DEV_APPSERVER:
      url = '/_ah/admin/memcache?namespace={0}'.format(namespace)
    else:
      url = ('https://appengine.google.com/memcache'
             '?&app_id={0}&namespace={1}'
             .format(self._GetAppId(namespace), namespace))
    self.redirect(url)


class GetConfig(PlaygroundHandler):

  def get(self):
    """Handles HTTP GET requests."""
    r = {
        'PLAYGROUND_USER_CONTENT_HOST': settings.PLAYGROUND_USER_CONTENT_HOST,
        'git_playground_url': 'http://code.google.com/p/cloud-playground/',
        'playground_namespace': settings.PLAYGROUND_NAMESPACE,
        'email': self.user.key.id(),
        'is_logged_in': bool(users.get_current_user()),
        'is_admin': bool(users.is_current_user_admin()),
    }
    self.response.headers['Content-Type'] = _JSON_MIME_TYPE
    self.response.write(tojson(r))


class GetProjects(PlaygroundHandler):

  def get(self):
    r = [self.DictOfProject(p) for p in model.GetProjects(self.user)]
    self.response.headers['Content-Type'] = _JSON_MIME_TYPE
    self.response.write(tojson(r))


class GetTemplates(PlaygroundHandler):

  def get(self):
    template_sources = [{
        'key': s.key.id(),
        'description': s.description,
    } for s in model.GetTemplateSources()]
    templates = [{
        'key': t.key.id(),
        'source_key': t.key.parent().id(),
        'name': t.name,
        'description': t.description,
    } for t in model.GetTemplates()]
    r = {
        'template_sources': template_sources,
        'templates': templates,
    }
    self.response.headers['Content-Type'] = _JSON_MIME_TYPE
    self.response.write(tojson(r))


class GetFile(PlaygroundHandler):
  """Get file handler."""

  def _CheckCors(self):
    origin = self.request.headers.get('Origin')
    # If not a CORS request, do nothing
    if not origin:
      return
    playground_origins = ['{0}://{1}'.format(self.request.scheme, h)
                          for h in settings.PLAYGROUND_HOSTS]

    if origin not in playground_origins:
      self.response.set_status(401)
      self.response.headers['Content-Type'] = 'text/plain'
      self.response.write('Unrecognized origin {0}'.format(origin))
      return
    if self.request.host != settings.PLAYGROUND_USER_CONTENT_HOST:
      self.response.set_status(401)
      self.response.headers['Content-Type'] = 'text/plain'
      self.response.write('Files may only be fetched from {0}'
                          .format(settings.PLAYGROUND_USER_CONTENT_HOST))
      return
    # OK, CORS access allowed
    self.response.headers['Access-Control-Allow-Origin'] = origin
    self.response.headers['Access-Control-Allow-Methods'] = 'GET'
    self.response.headers['Access-Control-Max-Age'] = '600'
    allowed_headers = 'Origin, X-XSRF-Token, X-Requested-With, Accept'
    self.response.headers['Access-Control-Allow-Headers'] = allowed_headers
    self.response.headers['Access-Control-Allow-Credentials'] = 'true'

  def options(self, project_id, filename):
    """Handles HTTP OPTIONS requests."""
    assert project_id
    assert filename
    self._CheckCors()

  def get(self, project_id, filename):
    """Handles HTTP GET requests."""
    assert project_id
    assert filename
    self._CheckCors()

    contents = self.tree.GetFileContents(filename)
    if contents is None:
      self.response.set_status(404)
      self.response.headers['Content-Type'] = 'text/plain'
      self.response.write('File does not exist: %s' % filename)
      return

    self.response.headers['Content-Type'] = shared.GuessMimeType(filename)
    self.response.headers['X-Content-Type-Options'] = 'nosniff'
    self.response.write(contents)


class PutFile(PlaygroundHandler):

  def put(self, project_id, filename):
    """Handles HTTP PUT requests."""
    assert project_id
    assert filename
    self.tree.SetFile(path=filename, contents=self.request.body)

    self.response.headers['Content-Type'] = 'text/plain'
    self.response.write('OK')


class MoveFile(PlaygroundHandler):

  def post(self, project_id, oldpath):
    """Handles HTTP POST requests."""
    assert project_id
    assert oldpath
    if not model.GetProject(project_id):
      raise Exception('Project {0} does not exist'.format(project_id))
    data = json.loads(self.request.body)
    newpath = data.get('newpath')
    assert newpath
    if self.tree.HasFile(newpath):
      raise error.PlaygroundError('Filename {0!r} already exists'
                             .format(str(newpath)))
    self.tree.MoveFile(oldpath, newpath)


class DeletePath(PlaygroundHandler):

  def post(self, project_id, path):
    """Handles HTTP POST requests."""
    assert project_id
    if not model.GetProject(project_id):
      raise Exception('Project {0} does not exist'.format(project_id))
    self.tree.DeletePath(path)


class ListFiles(PlaygroundHandler):

  def get(self, project_id, path):
    """Handles HTTP GET requests."""
    assert project_id
    project = model.GetProject(project_id)
    if not project:
      self.response.set_status(httplib.NOT_FOUND)
      return
    # 'path is None' means get all files recursively
    if not path:
      path = None
    r = self.tree.ListDirectory(path)
    r = [{'name': name, 'mime_type': shared.GuessMimeType(name)} for name in r]
    self.response.headers['Content-Type'] = _JSON_MIME_TYPE
    self.response.write(tojson(r))


class Login(PlaygroundHandler):

  def get(self):
    """Handles HTTP GET requests."""
    self.redirect(users.create_login_url('/playground'))


class Logout(PlaygroundHandler):

  def get(self):
    """Handles HTTP GET requests."""
    self.redirect(users.create_logout_url('/playground'))


class CreateProject(PlaygroundHandler):
  """Request handler for creating projects via an HTML link."""

  @ndb.transactional(xg=True)
  def _MakeTemplateProject(self, template_url, project_name,
                           project_description):
    project = model.CreateProject(self.user,
                                  template_url=template_url,
                                  project_name=project_name,
                                  project_description=project_description)
    # set self.project_id and default namespace which cannot be set from url
    self.project_id = project.key.id()
    namespace_manager.set_namespace(str(self.project_id))
    # set self.project so we can access self.tree
    self.project = project
    model.PopulateProject(self.tree, template_url)
    return project

  def get(self):
    # allow project creation via:
    # https://appid.appspot.com/playground/c?template_url=...
    self.post()

  def post(self):
    project_name = self.request.data['project_name']
    if not project_name:
      raise error.PlaygroundError('project_name required')
    project_description = (self.request.data['project_description']
                           or project_name)
    template_url = self.request.data['template_url']
    if not template_url:
      raise error.PlaygroundError('template_url required')
    project = self._MakeTemplateProject(template_url, project_name,
                                        project_description)
    r = self.DictOfProject(project)
    self.response.headers['Content-Type'] = _JSON_MIME_TYPE
    self.response.write(tojson(r))


class DeleteProject(PlaygroundHandler):

  def post(self, project_id):
    assert project_id
    if not model.GetProject(project_id):
      raise Exception('Project {0} does not exist'.format(project_id))
    model.DeleteProject(self.user, tree=self.tree, project_id=project_id)


class RenameProject(PlaygroundHandler):

  def post(self, project_id):
    assert project_id
    data = json.loads(self.request.body)
    newname = data.get('newname')
    assert newname
    project = model.RenameProject(project_id, newname)
    r = self.DictOfProject(project)
    self.response.headers['Content-Type'] = _JSON_MIME_TYPE
    self.response.write(tojson(r))


class Nuke(PlaygroundHandler):

  def post(self):
    if not users.is_current_user_admin():
      shared.e('You must be an admin for this app')
    model.DeleteTemplates()
    self.redirect('/playground')


config = {}
config['webapp2_extras.sessions'] = {
    'secret_key': secret.GetSecret('webapp2_extras.sessions', entropy=128),
    'cookie_args': {
        'httponly': True,
        'secure': not common.IsDevMode(),
    },
}

app = webapp2.WSGIApplication([
    # config actions
    ('/playground/getconfig', GetConfig),

    # tree actions
    ('/playground/p/(.*)/getfile/(.*)', GetFile),
    ('/playground/p/(.*)/putfile/(.*)', PutFile),
    ('/playground/p/(.*)/movefile/(.*)', MoveFile),
    ('/playground/p/(.*)/deletepath/(.*)', DeletePath),
    ('/playground/p/(.*)/listfiles/?(.*)', ListFiles),

    # project actions
    ('/playground/gettemplates', GetTemplates),
    ('/playground/getprojects', GetProjects),
    ('/playground/p/(.*)/delete', DeleteProject),
    ('/playground/p/(.*)/rename', RenameProject),

    # playground actions
    ('/playground/createproject', CreateProject),

    # admin tools
    ('/playground/nuke', Nuke),

    # /playground
    ('/playground/login', Login),
    ('/playground/logout', Logout),
    ('/playground/datastore/(.*)', DatastoreRedirect),
    ('/playground/memcache/(.*)', MemcacheRedirect),
], debug=True, config=config)
