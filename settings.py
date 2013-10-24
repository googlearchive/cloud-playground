"""Module containing global playground constants and functions."""

import os

from google.appengine.api import app_identity
from google.appengine.api import backends

import appids
import secret


DEBUG = True


# user content hostname prefix
USER_CONTENT_PREFIX = 'user-content'

# RFC1113 formatted 'Expires' to prevent HTTP/1.0 caching
LONG_AGO = 'Mon, 01 Jan 1990 00:00:00 GMT'

# 10 minutes
TEMPLATE_MEMCACHE_TIME = 3600

# owners of template projects
PUBLIC_PROJECT_TEMPLATE_OWNER = 'PUBLIC_TEMPLATE'
MANUAL_PROJECT_TEMPLATE_OWNER = 'MANUAL_TEMPLATE'
PROJECT_TEMPLATE_OWNERS = [
    PUBLIC_PROJECT_TEMPLATE_OWNER,
    MANUAL_PROJECT_TEMPLATE_OWNER
]

# whether or not we're running in the dev_appserver
_DEV_MODE = os.environ['SERVER_SOFTWARE'].startswith('Development/')

# namespace for playground specific data
PLAYGROUND_NAMESPACE = '_playground'

# template projects location
TEMPLATE_PROJECT_DIR = 'repos/'

# project access_key query parameter name
ACCESS_KEY_SET_COOKIE_PARAM_NAME = 'set_access_key_cookie'

ACCESS_KEY_HTTP_HEADER = 'X-Cloud-Playground-Access-Key'

ACCESS_KEY_COOKIE_NAME = 'access_key'

ACCESS_KEY_COOKIE_ARGS = {
    'httponly': True,
    'secure': not _DEV_MODE,
}

# name for the session cookie
SESSION_COOKIE_NAME = 'session'

SESSION_COOKIE_ARGS = {
    'httponly': True,
    'secure': not _DEV_MODE,
}

XSRF_COOKIE_ARGS = {
    'httponly': False,
    'secure': not _DEV_MODE,
}

WSGI_CONFIG = {
    'webapp2_extras.sessions': {
        'secret_key': secret.GetSecret('webapp2_extras.sessions', entropy=128),
        'cookie_args': SESSION_COOKIE_ARGS,
    }
}

# One hour
MIN_EXPIRATION_SECONDS = 3600

# One week
DEFAULT_EXPIRATION_SECONDS = 604800

# Extensions to exclude when creating template projects
SKIP_EXTENSIONS = ('swp', 'pyc', 'svn')

if _DEV_MODE:
  PLAYGROUND_HOSTS = ['localhost:8080', '127.0.0.1:8080',
                      # port 7070 for karma e2e test
                      'localhost:7070', '127.0.0.1:7070',
                      app_identity.get_default_version_hostname()]
  # PLAYGROUND_USER_CONTENT_HOST = backends.get_hostname('user-content-backend')
  PLAYGROUND_USER_CONTENT_HOST = None
  MIMIC_HOST = backends.get_hostname('exec-code-backend')
else:
  PLAYGROUND_HOSTS = ['{}.appspot.com'.format(appids.PLAYGROUND_APP_ID)]
  if appids.PLAYGROUND_APP_ID_ALIAS:
    PLAYGROUND_HOSTS.append('{}.appspot.com'
                            .format(appids.PLAYGROUND_APP_ID_ALIAS))
  # PLAYGROUND_USER_CONTENT_HOST = ('{0}-dot-{1}.appspot.com'
  #                                 .format(USER_CONTENT_PREFIX,
  #                                         appids.PLAYGROUND_APP_ID))
  PLAYGROUND_USER_CONTENT_HOST = None
  MIMIC_HOST = '{0}.appspot.com'.format(appids.MIMIC_APP_ID)
