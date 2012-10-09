"""Module containing the bliss WSGI handlers."""

import cgi
import httplib
import json
import logging
import os
import re
import urllib

from jinja2 import Environment
from jinja2 import FileSystemLoader

import webapp2
from webapp2_extras import security
from webapp2_extras import sessions

from __mimic import common
from __mimic import mimic

import codesite
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

_JINJA2_ENV = Environment(autoescape=True, loader=FileSystemLoader(''))

_INVALID_PROJECT_NAMES = (settings.USER_CONTENT_PREFIX)

_DASH_DOT_DASH = '-dot-'

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

  def get_user_key(self):
    """Returns the email from logged in user or the session user key."""
    user = users.get_current_user()
    if user:
      return user.email()
    return self.session.get(_ANON_USER_KEY)

  def _PerformCsrfRequestValidation(self):
    session_xsrf = self.session['xsrf']
    client_xsrf = self.request.headers[_XSRF_TOKEN_HEADER]
    if not client_xsrf:
      raise Exception('Missing client XSRF token')
    if client_xsrf != session_xsrf:
      raise Exception('Client XSRF token {0!r} does not match '
                      'session XSRF token {1!r}'
                      .format(client_xsrf, session_xsrf))

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
      self.user = model.GetUser(self.get_user_key())
      self.PerformValidation()
    except error.BlissError, e:
      # Manually dispatch to handle_exception
      self.handle_exception(e, self.app.debug)
      return

    try:
      # Exceptions during dispatch automatically handled by handle_exception
      super(SessionHandler, self).dispatch()
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
      suffix = security.generate_random_string(
          length=10,
          pool=security.LOWERCASE_ALPHANUMERIC)
      session[_ANON_USER_KEY] = 'user_{0}'.format(suffix)
    return session


class BlissHandler(SessionHandler):
  """Convenice request handler with bliss specific functionality."""

  def not_found(self):
    self.render('404.html', path_info=self.request.path_info)

  @webapp2.cached_property
  def project_name(self):
    return mimic.GetProjectNameFromPathInfo(self.request.path_info)

  @webapp2.cached_property
  def project(self):
    if not self.project_name:
      return None
    return model.GetProject(self.project_name)

  @webapp2.cached_property
  def tree(self):
    if not self.project:
      raise Exception('Project {0} does not exist'.format(self.project_name))
    # TODO: instantiate tree elsewhere
    assert namespace_manager.get_namespace() == self.project_name, (
        'namespace_manager.get_namespace()={0!r}, project_name={1!r}'
        .format(namespace_manager.get_namespace(), self.project_name))
    return common.config.CREATE_TREE_FUNC(self.project_name)

  def _PerformWriteAccessCheck(self):
    user_key = self.user.key.id()
    if not user_key:
      shared.e('FIX ME: no user')
    if not self.project:
      # TODO: better approach which allows the creation of new projects
      return
    if user_key not in self.project.writers:
      raise error.BlissError('User {0!r} is not authorized to edit project '
                             '{1!r}'.format(user_key, self.project_name))

  def PerformValidation(self):
    super(BlissHandler, self).PerformValidation()
    if not shared.ThisIsBlissApp():
      url = 'https://{0}/bliss'.format(settings.BLISS_HOST)
      self.error(501)  # not implemented
      self.response.write('Bliss user interface not implemented here.<br>'
                          'See <a href="{0}">{0}</a> instead.'
                          .format(url))
      return
    if self.request.method not in _HTTP_READ_METHODS:
      self._PerformWriteAccessCheck()

  def handle_bliss_error(self, exception):
    """Called if this handled throws a BlissError.

    Args:
      exception: the exception that was thrown
    """
    self.error(500)
    logging.exception(exception)
    self.response.clear()
    self.response.headers['Content-Type'] = 'text/plain'
    self.response.headers['X-Bliss-Error'] = 'True'
    self.response.out.write('%s' % (cgi.escape(exception.message, quote=True)))

  def handle_exception(self, exception, debug_mode):
    """Called if this handler throws an exception during execution.

    Args:
      exception: the exception that was thrown
      debug_mode: True if the web application is running in debug mode
    """
    if isinstance(exception, error.BlissError):
      self.handle_bliss_error(exception)
    else:
      super(BlissHandler, self).handle_exception(exception, debug_mode)

  def render(self, template, *args, **kwargs):
    """Renders the provided template."""
    template = _JINJA2_ENV.get_template(template)

    namespace = mimic.GetNamespace() or settings.BLISS_NAMESPACE
    app_id = app_identity.get_application_id()

    if _DEV_APPSERVER:
      datastore_admin_url = '/_ah/admin/datastore?namespace=%s' % namespace
      memcache_admin_url = '/_ah/admin/memcache?namespace=%s' % namespace
    elif users.is_current_user_admin():
      datastore_admin_url = ('https://appengine.google.com/datastore/explorer'
                             '?&app_id=%s&namespace=%s' % (app_id, namespace))
      memcache_admin_url = ('https://appengine.google.com/memcache'
                            '?&app_id=%s&namespace=%s' % (app_id, namespace))
    else:
      datastore_admin_url = None
      memcache_admin_url = None

    if self.project:
      kwargs['project_name'] = self.project.project_name
      kwargs['project_description'] = self.project.project_description
      kwargs['project_run_url'] = ('/bliss/p/{0}/run'
                                   .format(self.project.project_name))

    if users.get_current_user():
      kwargs['is_logged_in'] = True
    if users.is_current_user_admin():
      kwargs['is_admin'] = True

    self.response.write(template.render(
        *args,
        namespace=namespace,
        email=self.user.key.id(),
        git_bliss_url='http://code.google.com/p/cloud-playground/',
        datastore_admin_url=datastore_admin_url,
        memcache_admin_url=memcache_admin_url,
        **kwargs))


class GetConfig(BlissHandler):

  def get(self, project_name):
    """Handles HTTP GET requests."""
    assert project_name
    r = {
        'BLISS_USER_CONTENT_HOST': settings.BLISS_USER_CONTENT_HOST,
    };
    self.response.headers['Content-Type'] = _JSON_MIME_TYPE
    self.response.write(tojson(r))


class GetFile(BlissHandler):

  def _CheckCors(self, project_name):
    origin = self.request.headers.get('Origin')
    # If not a CORS request, do nothing
    if not origin:
      return
    bliss_origin = '{0}://{1}'.format(self.request.scheme,
                                      settings.BLISS_HOST)

    if origin != bliss_origin:
      raise Exception('CORS supported only from origin {0}'
                      .format(bliss_origin))
      self.response.set_status(401)
      self.response.headers['Content-Type'] = 'text/plain'
      self.response.write('CORS supported only from origin {0}'
                          .format(bliss_origin))
      return
    if self.request.host != settings.BLISS_USER_CONTENT_HOST:
      self.response.set_status(401)
      self.response.headers['Content-Type'] = 'text/plain'
      self.response.write('Files may only be fetched from {0}'
                          .format(settings.BLISS_USER_CONTENT_HOST))
      return
    # OK, CORS access allowed
    self.response.headers['Access-Control-Allow-Origin'] = bliss_origin
    self.response.headers['Access-Control-Allow-Methods'] = 'GET'
    self.response.headers['Access-Control-Max-Age'] = '600'
    self.response.headers['Access-Control-Allow-Headers'] = 'Origin, X-XSRF-Token, X-Requested-With, Accept'
    self.response.headers['Access-Control-Allow-Credentials'] = 'true'

  def options(self, project_name, filename):
    """Handles HTTP OPTIONS requests."""
    assert project_name
    assert filename
    self._CheckCors(project_name)

  def get(self, project_name, filename):
    """Handles HTTP GET requests."""
    assert project_name
    assert filename
    self._CheckCors(project_name)

    contents = self.tree.GetFileContents(filename)
    if contents is None:
      self.response.set_status(404)
      self.response.headers['Content-Type'] = 'text/plain'
      self.response.write('File does not exist: %s' % filename)
      return

    self.response.headers['Content-Type'] = shared.GuessMimeType(filename)
    self.response.headers['X-Content-Type-Options'] = 'nosniff'
    self.response.write(contents)


class PutFile(BlissHandler):

  def put(self, project_name, filename):
    """Handles HTTP PUT requests."""
    assert project_name
    assert filename
    self.tree.SetFile(path=filename, contents=self.request.body)

    self.response.headers['Content-Type'] = 'text/plain'
    self.response.write('OK')


class MoveFile(BlissHandler):

  def post(self, project_name, oldpath):
    """Handles HTTP POST requests."""
    assert project_name
    assert oldpath
    if not model.GetProject(project_name):
      raise Exception('Project {0} does not exist'.format(project_name))
    data = json.loads(self.request.body)
    newpath = data.get('newpath')
    assert newpath
    if self.tree.HasFile(newpath):
      raise error.BlissError('Filename {0!r} already exists'
                             .format(str(newpath)))
    self.tree.MoveFile(oldpath, newpath)


class DeletePath(BlissHandler):

  def post(self, project_name, path):
    """Handles HTTP POST requests."""
    assert project_name
    if not model.GetProject(project_name):
      raise Exception('Project {0} does not exist'.format(project_name))
    self.tree.DeletePath(path)


class ListFiles(BlissHandler):

  def get(self, project_name, path):
    """Handles HTTP GET requests."""
    project = model.GetProject(project_name)
    if not project:
      return self.not_found()
    # 'path is None' means get all files recursively
    if not path:
      path = None
    r = self.tree.ListDirectory(path)
    r = [{'name': name} for name in r]
    self.response.headers['Content-Type'] = _JSON_MIME_TYPE
    self.response.write(tojson(r))


class Project(BlissHandler):

  def get(self, project_name):
    """Handles HTTP GET requests."""
    assert project_name
    project = model.GetProject(project_name)
    if not project:
      return self.not_found()
    self.render('project.html')


class Bliss(BlissHandler):

  def get(self):
    """Handles HTTP GET requests."""
    projects = model.GetProjects(self.user)
    p = [(p.project_name, p.project_description) for p in projects]
    template_sources = model.GetTemplateSources()
    tuples = [(s, model.GetTemplates(s)) for s in template_sources]
    self.render('main.html',
                projects=p,
                template_tuples=tuples)


class Login(BlissHandler):

  def get(self):
    """Handles HTTP GET requests."""
    self.redirect(users.create_login_url('/bliss'))


class Logout(BlissHandler):

  def get(self):
    """Handles HTTP GET requests."""
    self.redirect(users.create_logout_url('/bliss'))


class RunProject(BlissHandler):

  def _GetPlaygroundHostname(self, project_name):
    """Determine the playground hostname for the project."""
    if common.IsDevMode():
      return settings.PLAYGROUND_HOST
    return '{0}{1}{2}'.format(urllib.quote_plus(project_name),
                              _DASH_DOT_DASH,
                              settings.PLAYGROUND_HOST)

  def get(self, project_name):
    """Handles HTTP GET requests."""
    assert project_name
    if common.IsDevMode():
      self.response.set_cookie(common.config.PROJECT_NAME_COOKIE, project_name)
    url = '{0}://{1}/'.format(self.request.scheme,
                              self._GetPlaygroundHostname(project_name))
    self.redirect(url)


class EasyCreateProject(BlissHandler):
  """Request handler for creating projects via an HTML link."""

  def get(self):
    # allow project creation via:
    # https://appid.appspot.com/bliss/c?template_url=...
    project_name = model.NewProjectName()
    template_url = self.request.get('template_url')
    self.redirect('/bliss/p/{0}/create?template_url={1}'.format(project_name,
                                                                template_url))


class CreateProject(BlissHandler):
  """Request handler for creating projects."""

  def get(self, project_name):
    # allow EasyCreateProject GET to redirect here
    self.post(project_name)
    self.redirect('/bliss/p/{0}'.format(project_name))

  def post(self, project_name):
    """Handles HTTP POST requests."""
    assert project_name
    if (_DASH_DOT_DASH in project_name
        or not _VALID_PROJECT_RE.match(project_name)):
      raise error.BlissError('Project name must match {0} and must not contain '
                             '{1!r}'.format(_VALID_PROJECT_RE.pattern,
                                            _DASH_DOT_DASH))
    if project_name in _INVALID_PROJECT_NAMES:
      raise error.BlissError('Project name {0!r} is not available'
                             .format(project_name))
    template_url = self.request.get('template_url')
    project_description = (self.request.get('project_description')
                           or project_name)
    self.make_template_project(template_url, project_name, project_description)

  @ndb.transactional(xg=True)
  def make_template_project(self, template_url, project_name,
                            project_description):
    self.project = model.CreateProject(self.user,
                                       project_name=project_name,
                                       project_description=project_description)
    if codesite.IsCodesiteURL(template_url):
      codesite.PopulateProjectFromCodesite(tree=self.tree,
                                           template_url=template_url)
    else:
      model.PopulateProjectWithTemplate(tree=self.tree,
                                        template_url=template_url)


class DeleteProject(BlissHandler):

  def post(self, project_name):
    assert project_name
    if not model.GetProject(project_name):
      raise Exception('Project {0} does not exist'.format(project_name))
    model.DeleteProject(self.user, tree=self.tree,
                        project_name=project_name)


class RenameProject(BlissHandler):

  def post(self, project_name):
    raise Exception('not implemented. unable to rename %s' % project_name)


class AddSlash(webapp2.RequestHandler):

  def get(self):
    self.redirect(self.request.path_info + '/')


class Nuke(BlissHandler):

  def post(self):
    if not users.is_current_user_admin():
      shared.e('You must be an admin for this app')
    model.DeleteTemplates()
    self.redirect('/bliss')


config = {}
config['webapp2_extras.sessions'] = {
    'secret_key': secret.GetSecret('webapp2_extras.sessions', entropy=128),
}

app = webapp2.WSGIApplication([
    # config actions
    ('/bliss/p/(.*)/getconfig', GetConfig),

    # tree actions
    ('/bliss/p/(.*)/getfile/(.*)', GetFile),
    ('/bliss/p/(.*)/putfile/(.*)', PutFile),
    ('/bliss/p/(.*)/movefile/(.*)', MoveFile),
    ('/bliss/p/(.*)/deletepath/(.*)', DeletePath),
    ('/bliss/p/(.*)/listfiles/?(.*)', ListFiles),

    # project actions
    ('/bliss/p/(.*)/create', CreateProject),
    ('/bliss/p/(.*)/delete', DeleteProject),
    ('/bliss/p/(.*)/rename', RenameProject),
    ('/bliss/p/(.*)/run', RunProject),

    # bliss actions
    ('/bliss/c', EasyCreateProject),

    # /bliss/p/project_name/
    ('/bliss/p/(.*)/', Project),
    ('/bliss/p/[^/]+$', AddSlash),

    # admin tools
    ('/bliss/nuke', Nuke),

    # /bliss
    ('/bliss', AddSlash),
    ('/bliss/', Bliss),
    ('/bliss/login', Login),
    ('/bliss/logout', Logout),
], debug=True, config=config)
