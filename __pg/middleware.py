"""Playground middleware."""

import httplib
import logging
import sys

import webapp2
from webapp2_extras import securecookie
from webapp2_extras import security
from webapp2_extras import sessions

from . import appids
from . import error
from error import Abort
from mimic.__mimic import common
from mimic.__mimic import mimic
from . import model
from . import settings
from . import shared

from google.appengine.api import users


# session key to store the anonymous user object
_ANON_USER_KEY = u'anon_user_key'

# AngularJS XSRF Cookie, see http://docs.angularjs.org/api/ng.$http
_XSRF_TOKEN_COOKIE = 'XSRF-TOKEN'

# AngularJS XSRF HTTP Header, see http://docs.angularjs.org/api/ng.$http
_XSRF_TOKEN_HEADER = 'HTTP_X_XSRF_TOKEN'


def MakeCookieHeader(name, value, cookie_args=None):
  items = ['{}={}'.format(name, value)]
  items.append('Path=/')
  if cookie_args:
    if cookie_args['secure']:
      items.append('secure')
    if cookie_args['httponly']:
      items.append('HttpOnly')
  cookie_header = ('set-cookie', '; '.join(items))
  return cookie_header


# TODO: use datastore sequence instead
def MakeAnonUserKey():
  suffix = security.generate_random_string(
      length=10,
      pool=security.LOWERCASE_ALPHANUMERIC)
  return 'user_{0}'.format(suffix)


def AdoptAnonymousProjects(dest_user_key, source_user_key):
  model.AdoptProjects(dest_user_key, source_user_key)


def GetOrMakeSession(request):
  """Get a new or current session."""
  session_store = sessions.get_store(request=request)
  session = session_store.get_session()

  if not session:
    session['xsrf'] = security.generate_random_string(entropy=128)
  user = users.get_current_user()
  if user:
    if _ANON_USER_KEY in session:
      AdoptAnonymousProjects(user.email(), session[_ANON_USER_KEY])
      del session[_ANON_USER_KEY]
  else:
    if _ANON_USER_KEY not in session:
      session[_ANON_USER_KEY] = MakeAnonUserKey()

  return session


def GetUserKey(session):
  """Returns the email from logged in user or the session user key."""
  user = users.get_current_user()
  if user:
    return user.email()
  return session[_ANON_USER_KEY]


def _PerformCsrfRequestValidation(session, environ):
  session_xsrf = session['xsrf']
  client_xsrf = environ.get(_XSRF_TOKEN_HEADER)
  if not client_xsrf:
    Abort(httplib.UNAUTHORIZED, 'Missing client XSRF token.')
  if client_xsrf != session_xsrf:
    # do not log tokens in production
    if common.IsDevMode():
      logging.error('Client XSRF token={0!r}, session XSRF token={1!r}'
                    .format(client_xsrf, session_xsrf))
    Abort(httplib.UNAUTHORIZED,
          'Client XSRF token does not match session XSRF token.')


class Redirector(object):
  """WSGI middleware which redirects '/' to '/playground'.

  Redirects occur only for PLAYGROUND_HOSTS. Requests to mimic are passed
  through unaltered.
  """

  def __init__(self, app):
    self.app = app

  def __call__(self, environ, start_response):
    if common.IsDevMode():
      logging.info('\n' * 1)
    # TODO: Use App Engine Modules to dispatch requests instead.
    if (environ['HTTP_HOST'] in settings.PLAYGROUND_HOSTS
        and environ['PATH_INFO'] == '/'):
      url = '/playground'
      if environ['QUERY_STRING']:
        url += '?' + environ['QUERY_STRING']
      start_response('302 Found', [('Location', url)])
      return iter([''])
    return self.app(environ, start_response)


class Session(object):
  """WSGI middleware which adds user/project sessions.

  Adds the following keys to the environ:
  - environ['playground.session'] contains a webapp2 session
  - environ['playground.user']    contains the current user entity
  """

  def __init__(self, app, config):
    self.app = app
    self.app.config = webapp2.Config(config)
    secret_key = config['webapp2_extras.sessions']['secret_key']
    self.serializer = securecookie.SecureCookieSerializer(secret_key)

  def MakeSessionCookieHeader(self, session):
    value = self.serializer.serialize(settings.SESSION_COOKIE_NAME,
                                      dict(session))
    value = '"{}"'.format(value)
    return MakeCookieHeader(settings.SESSION_COOKIE_NAME, value,
                            settings.SESSION_COOKIE_ARGS)

  def MakeXsrfCookieHeader(self, session):
    return MakeCookieHeader(_XSRF_TOKEN_COOKIE, session['xsrf'],
                            settings.XSRF_COOKIE_ARGS)

  def __call__(self, environ, start_response):
    additional_headers = []

    # pylint:disable-msg=invalid-name
    def custom_start_response(status, headers, exc_info=None):
      headers.extend(additional_headers)
      # keep session cookies private
      headers.extend([
          # Note App Engine automatically sets a 'Date' header for us. See
          # https://developers.google.com/appengine/docs/python/runtime#Responses
          ('Expires', settings.LONG_AGO),
          ('Cache-Control', 'private, max-age=0'),
      ])
      return start_response(status, headers, exc_info)

    # 1. ensure we have a session
    request = webapp2.Request(environ, app=self.app)
    session = environ['playground.session'] = GetOrMakeSession(request)

    if session.modified:
      additional_headers.extend([
          self.MakeSessionCookieHeader(session),
          self.MakeXsrfCookieHeader(session),
      ])

    # 2. ensure we have an user entity
    user_key = GetUserKey(session)
    assert user_key
    # TODO: avoid creating a datastore entity on every anonymous request
    environ['playground.user'] = model.GetOrCreateUser(user_key)

    # 3. perform CSRF checks
    if not shared.IsHttpReadMethod(environ):
      _PerformCsrfRequestValidation(session, environ)

    return self.app(environ, custom_start_response)


class ProjectFilter(object):
  """WSGI middleware which determines the current project.

  Adds the following keys to the environ:
  - environ['playground.project'] contains the current project
  """

  def __init__(self, app, assert_project_existence=True):
    self._app = app
    self._assert_project_existence = assert_project_existence

  def __call__(self, environ, start_response):
    project_id = mimic.GetProjectId(environ, False)
    if project_id and shared.ThisIsPlaygroundApp():
      project = model.GetProject(project_id)
      if self._assert_project_existence:
        if not project:
          Abort(httplib.NOT_FOUND, 'project_id {} not found'.format(project_id))
      environ['playground.project'] = project or settings.NO_SUCH_PROJECT
    return self._app(environ, start_response)


class AccessKeyCookieFilter(object):
  """WSGI middleware which manages and trackes access_key cookies.

  If a set cookie query parameter is found or an existing cookie the access_key
  is stored in environ['mimic.access_key'].
  """

  def __init__(self, app):
    self.app = app

  def __call__(self, environ, start_response):
    request = webapp2.Request(environ, app=self.app)
    access_key = (request.get(settings.ACCESS_KEY_SET_COOKIE_PARAM_NAME) or
                  request.cookies.get(settings.ACCESS_KEY_COOKIE_NAME))
    if access_key:
      environ['mimic.access_key'] = access_key

    # pylint:disable-msg=invalid-name
    def custom_start_response(status, headers, exc_info=None):
      """Custom WSGI start_response which adds cookie header."""
      if access_key:
        # keep session cookies private
        headers.extend([
            MakeCookieHeader(settings.ACCESS_KEY_COOKIE_NAME, access_key,
                             settings.ACCESS_KEY_COOKIE_ARGS),
            # Note App Engine automatically sets a 'Date' header for us. See
            # https://developers.google.com/appengine/docs/python/runtime#Responses
            ('Expires', settings.LONG_AGO),
            ('Cache-Control', 'private, max-age=0'),
        ])
      return start_response(status, headers, exc_info)

    return self.app(environ, custom_start_response)


class AccessKeyHttpHeaderFilter(object):
  """WSGI middleware which detects access_key HTTP header.

  If the header is detected, the access_key is stored in
  environ['mimic.access_key'].
  """

  def __init__(self, app):
    self.app = app

  def __call__(self, environ, start_response):
    request = webapp2.Request(environ, app=self.app)
    access_key = request.headers.get(settings.ACCESS_KEY_HTTP_HEADER)
    if access_key:
      environ['mimic.access_key'] = access_key
    return self.app(environ, start_response)


class MimicControlAccessFilter(object):
  """WSGI middleware which performs mimic project access checks.

  Only checks paths which start with common.CONTROL_PREFIX.

  Requires that the following keys be present in the environ:
  - environ['playground.user']    contains the current user entity
  - environ['playground.project'] contains the current project entity
  """

  def __init__(self, app):
    self.app = app
    self.config = getattr(app, 'config', None)
    self.exc_info = None

  def _AssertCollaboratingAppIdAccessCheck(self, environ):
    if environ['PATH_INFO'] in common.CONTROL_PATHS_REQUIRING_TREE:
      if not shared.ThisIsPlaygroundApp():
        Abort(httplib.FORBIDDEN,
              'playground service is not available in this app id')
    else:
      if shared.ThisIsPlaygroundApp():
        Abort(httplib.NOT_FOUND,
              'mimic execution playground is not available in this app id')

  def __call__(self, environ, start_response):
    if appids.TWO_COLLABORATING_APP_IDS:
      self._AssertCollaboratingAppIdAccessCheck(environ)

    if environ['PATH_INFO'] in common.CONTROL_PATHS_REQUIRING_TREE:
      if shared.IsHttpReadMethod(environ):
        if not shared.HasProjectReadAccess(environ):
          Abort(httplib.UNAUTHORIZED, 'no project read access to mimic control')
      else:
        if not shared.HasProjectWriteAccess(environ):
          Abort(httplib.UNAUTHORIZED,
                'no project write access to mimic control')
    return self.app(environ, start_response)


class ErrorHandler(object):
  """WSGI middleware which adds PlaygroundError handling."""

  def __init__(self, app, debug):
    self.app = app
    self.debug = debug

  def __call__(self, environ, start_response):
    if common.IsDevMode():
      logging.info('\n' * 1)
    try:
      return self.app(environ, start_response)
    except Exception, e:  # pylint:disable-msg=broad-except
      status, headers, body = error.MakeErrorResponse(e, self.debug)
      start_response(status, headers, sys.exc_info())
      return body
