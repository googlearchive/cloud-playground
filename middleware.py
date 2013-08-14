"""Playground middleware."""

import cgi
import logging
import sys

import webapp2
from webapp2_extras import securecookie
from webapp2_extras import security
from webapp2_extras import sessions

import error
from error import *
from mimic.__mimic import common
from mimic.__mimic import mimic
import model
import settings
import shared
import traceback

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
  session_store = sessions.get_store(request=request)
  session = session_store.get_session()

  if not session:
    session['xsrf'] = security.generate_random_string(entropy=128)
  user = users.get_current_user()
  if user:
    if _ANON_USER_KEY in session:
      AdoptAnonymousProjects(user.email(), session[_ANON_USER_KEY])
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
    Abort(httplib.UNAUTHORIZED, 'Missing client XSRF token. '
                                'Clear your cookies and refresh the page.')
  if client_xsrf != session_xsrf:
    # do not log tokens in production
    if common.IsDevMode():
      logging.error('Client XSRF token={0!r}, session XSRF token={1!r}'
                    .format(client_xsrf, session_xsrf))
    Abort(httplib.UNAUTHORIZED, 'Client XSRF token does not match session '
                                'XSRF token. Clear your cookies and refresh '
                                'the page.')


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

    def custom_start_response(status, headers, exc_info=None):
      headers.extend(additional_headers)
      # keep session cookies private
      headers.extend([
          # Note App Engine automatically sets a 'Date' header for us. See
          # https://developers.google.com/appengine/docs/python/runtime#Responses
          ('Expires', shared.LONG_AGO),
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

    # 3. ensure we have a project, if one is specified
    project_id = mimic.GetProjectId(environ, False)
    if project_id:
      environ['playground.project'] = model.GetProject(project_id)

    # 4. perform CSRF checks
    if not shared.IsHttpReadMethod(environ):
      _PerformCsrfRequestValidation(session, environ)

    return self.app(environ, custom_start_response)


class MimicControlAccessFilter(object):
  """WSGI middleware which performs mimic project access checks.

  Only checks paths which start with common.CONTROL_PREFIX.

  Requires that the following keys be present in the environ:
  - environ['playground.user']    contains the current user entity

  Adds the following keys to the environ:
  - environ['playground.project'] contains the current project if applicable
  """

  def __init__(self, app):
    self.app = app
    self.config = getattr(app, 'config', None)
    self.exc_info = None

  def __call__(self, environ, start_response):
    # TODO: use modules dispatch to handle this instead
    if environ['PATH_INFO'].startswith(common.CONTROL_PREFIX):
      if not shared.ThisIsPlaygroundApp():
        Abort(httplib.FORBIDDEN,
              'playground service is not available in this app id')
    else:
      if shared.ThisIsPlaygroundApp():
        Abort(httplib.NOT_FOUND,
              'mimic execution playground is not available in this app id')

    if environ['PATH_INFO'].startswith(common.CONTROL_PREFIX):
      if shared.IsHttpReadMethod(environ):
        shared.AssertHasProjectReadAccess(environ)
      else:
        shared.AssertHasProjectWriteAccess(environ)
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
    except Exception, e:
      status, headers, body = error.MakeErrorResponse(e, self.debug)
      start_response(status, headers, sys.exc_info())
      return body
