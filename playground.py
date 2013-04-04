"""Module containing the playground WSGI handlers."""

import cgi
import httplib
import json
import logging
import os
import re
import urllib

from mimic import mimic_wsgi
from mimic.__mimic import common
from mimic.__mimic import mimic

import webapp2
from webapp2_extras import security
from webapp2_extras import sessions

import error
import model
import secret
import settings
import shared

from template import templates

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
      # Exceptions during dispatch are automatically handled by handle_exception
      super(SessionHandler, self).dispatch()
      # Note App Engine automatically sets a 'Date' header for us. See
      # https://developers.google.com/appengine/docs/python/runtime#Responses
      self.response.headers['Expires'] = _LONG_AGO
      self.response.headers['Cache-Control'] = 'private, max-age=0'
      self.response.headers['X-Frame-Options'] = 'SAMEORIGIN'
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
  """Convenience request handler with playground specific functionality."""

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
    # Note App Engine automatically sets a 'Date' header for us. See
    # https://developers.google.com/appengine/docs/python/runtime#Responses
    self.response.headers['Expires'] = _LONG_AGO
    self.response.headers['Cache-Control'] = 'private, max-age=0'
    self.response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    self.response.headers['Content-Type'] = 'text/plain'
    self.response.headers['X-Cloud-Playground-Error'] = 'True'
    self.response.out.write('{0}'.format(cgi.escape(exception.message,
                                                    quote=True)))

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
        # cast to str since JavaScript doesn't support long
        'key': str(project.key.id()),
        'template_url': project.template_url,
        'name': project.project_name,
        'description': project.project_description,
        'orderby': project.orderby,
        'run_url': self._GetPlaygroundRunUrl(project.key.id()),
        'in_progress_task_name': project.in_progress_task_name,
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
      return settings.PLAYGROUND_APP_ID
    else:
      return settings.EXEC_CODE_APP_ID


class DatastoreRedirect(RedirectHandler):

  def get(self, namespace):
    if _DEV_APPSERVER:
      url = '//localhost:8000/datastore?namespace={0}'.format(namespace)
    else:
      url = ('https://appengine.google.com/datastore/explorer'
             '?&app_id={0}&namespace={1}'
             .format(self._GetAppId(namespace), namespace))
    self.redirect(url)


class MemcacheRedirect(RedirectHandler):

  def get(self, namespace):
    if _DEV_APPSERVER:
      url = '//localhost:8000/memcache?namespace={0}'.format(namespace)
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
        'is_devappserver': bool(_DEV_APPSERVER),
    }
    self.response.headers['Content-Type'] = _JSON_MIME_TYPE
    self.response.write(tojson(r))


class OAuth2Admin(PlaygroundHandler):

  def post(self):
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


class GetProject(PlaygroundHandler):

  def get(self, project_id):
    project = model.GetProject(project_id)
    r = self.DictOfProject(project)
    self.response.headers['Content-Type'] = _JSON_MIME_TYPE
    self.response.write(tojson(r))


class GetProjects(PlaygroundHandler):

  def get(self):
    r = [self.DictOfProject(p) for p in model.GetProjects(self.user)]
    self.response.headers['Content-Type'] = _JSON_MIME_TYPE
    self.response.write(tojson(r))


class GetTemplateProjects(PlaygroundHandler):

  def get(self):
    by_project_name = lambda p: p.project_name
    r = [self.DictOfProject(p)
         for p in sorted(model.GetTemplateProjects(), key=by_project_name)]
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


class CopyProject(PlaygroundHandler):
  """Request handler for copying projects."""

  def post(self):
    project_id = self.request.data['project_id']
    if not project_id:
      raise error.PlaygroundError('project_id required')
    project = model.CopyProject(self.user, project_id)
    r = self.DictOfProject(project)
    self.response.headers['Content-Type'] = _JSON_MIME_TYPE
    self.response.write(tojson(r))


class RecreateTemplateProject(PlaygroundHandler):
  """Request handler for recreating template projects."""

  def post(self):
    project_id = self.request.data['project_id']
    if not project_id:
      raise error.PlaygroundError('project_id required')
    project = model.GetProject(project_id)
    if not project:
      raise error.PlaygroundError('failed to retrieve project {}'
                                  .format(project_id))
    repo_url = project.template_url
    repo = model.GetRepo(repo_url)
    model.CreateRepoAsync(repo.key.id(), repo.end_user_url, repo.name,
                          repo.description)


class CreateTemplateProjectByUrl(PlaygroundHandler):
  """Request handler for (re)creating template projects."""

  def post(self):
    repo_url = self.request.data.get('repo_url')
    if not repo_url:
      raise error.PlaygroundError('repo_id required')
    repo = model.GetRepo(repo_url)
    if not repo:
      end_user_url = name = description = repo_url
      repo = model.CreateRepoAsync(repo_url, end_user_url, name, description)
    project = repo.project.get()
    r = self.DictOfProject(project)
    self.response.headers['Content-Type'] = _JSON_MIME_TYPE
    self.response.write(tojson(r))


class NewProject(PlaygroundHandler):
  """Request handler for creating new projects via an HTML link."""

  # TODO: replace external uses of:
  # https://appid.appspot.com/playground/newproject?template_url=...
  # with https://appid.appspot.com/playground/?template_url=...
  def get(self):
    template_url = self.request.get('template_url')
    if not template_url:
      raise error.PlaygroundError('template_url required')
    self.redirect('/playground/?template_url={}'.format(template_url))


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


class TouchProject(PlaygroundHandler):

  def post(self, project_id):
    assert project_id
    project = model.TouchProject(project_id)
    r = self.DictOfProject(project)
    self.response.headers['Content-Type'] = _JSON_MIME_TYPE
    self.response.write(tojson(r))


class Warmup(PlaygroundHandler):

  def get(self):
    templates.GetRepoCollections()


class Fixit(PlaygroundHandler):

  def get(self):
    if not users.is_current_user_admin():
      shared.e('You must be an admin for this app')
    model.fixit()
    self.response.write('done')


class Nuke(PlaygroundHandler):

  def post(self):
    if not users.is_current_user_admin():
      shared.e('You must be an admin for this app')
    model.DeleteReposAndTemplateProjects()
    # force reinitialization
    templates.GetRepoCollections()
    self.redirect('/playground')


class MimicIntercept(mimic_wsgi.Mimic):
  """WSGI app which handles all requests destined for the target app."""

  def __iter__(self):
    if common.IsDevMode():
      logging.info('\n' * 3)
    if (os.environ['HTTP_HOST'] in settings.PLAYGROUND_HOSTS
        and os.environ['PATH_INFO'] == '/'):
      self._RedirectResponse('/playground')
      # empty body
      return iter([''])
    return super(MimicIntercept, self).__iter__()

  def _RedirectResponse(self, location):
    status = '302 Found'
    response_headers = [('Location', location)]
    self.start_response(status, response_headers)


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
    ('/playground/oauth2_admin', OAuth2Admin),

    # project actions
    ('/playground/recreate_template_project', RecreateTemplateProject),
    ('/playground/create_template_project_by_url', CreateTemplateProjectByUrl),
    ('/playground/gettemplateprojects', GetTemplateProjects),
    ('/playground/getprojects', GetProjects),
    ('/playground/copyproject', CopyProject),
    # TODO: remove
    ('/playground/newproject', NewProject),
    ('/playground/p/(.*)/getproject', GetProject),
    ('/playground/p/(.*)/delete', DeleteProject),
    ('/playground/p/(.*)/rename', RenameProject),
    ('/playground/p/(.*)/touch', TouchProject),

    # admin tools
    ('/playground/nuke', Nuke),
    ('/playground/fixit', Fixit),

    # /playground
    ('/playground/login', Login),
    ('/playground/logout', Logout),
    ('/playground/datastore/(.*)', DatastoreRedirect),
    ('/playground/memcache/(.*)', MemcacheRedirect),

    # warmup requests
    ('/_ah/warmup', Warmup),

    # backends in the dev_appserver
    ('/_ah/start', Warmup),
], debug=True, config=config)
