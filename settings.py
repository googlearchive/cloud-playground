"""Module containing global playground constants and functions."""

import os

from google.appengine.api import app_identity
from google.appengine.api import backends


# The application where the playground IDE runs
PLAYGROUND_APP_ID = 'try-appengine'

# The application where user code runs
EXEC_CODE_APP_ID = 'shared-playground'

# The application alias where the playground IDE runs
PLAYGROUND_APP_ID_ALIAS = 'cloud-playground'

# user content hostname prefix
USER_CONTENT_PREFIX = 'user-content'

# RFC1113 formatted 'Expires' to prevent HTTP/1.0 caching
LONG_AGO = 'Mon, 01 Jan 1990 00:00:00 GMT'

# 10 minutes
TEMPLATE_MEMCACHE_TIME = 3600

# Owner of template projects
PROJECT_TEMPLATE_OWNER = 'TEMPLATE'

# whether or not we're running in the dev_appserver
_DEV_MODE = os.environ['SERVER_SOFTWARE'].startswith('Development/')

# namespace for playground specific data
PLAYGROUND_NAMESPACE = '_playground'

# template projects location
TEMPLATE_PROJECT_DIR = 'repos/'

# project access_key query parameter name
ACCESS_KEY_SET_COOKIE_PARAM_NAME = 'set_access_key_cookie'

ACCESS_KEY_HTTP_HEADER = 'X-Cloud-Playground-Access-Key'

ACCESS_KEY_HTTP_HEADER_WSGI = 'HTTP_X_CLOUD_PLAYGROUND_ACCESS_KEY'

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



# Extensions to exclude when creating template projects
SKIP_EXTENSIONS = ('swp', 'pyc', 'svn')

# All app ids used by this project
_APP_IDS = set((PLAYGROUND_APP_ID, EXEC_CODE_APP_ID))

# Our app id
_APP_ID = os.environ['APPLICATION_ID'].split('~')[-1]
# support regular 'appspot.com' app ids only
assert ':' not in _APP_ID, ('{} app ids are unsupported'
                            .format(_APP_ID.split(':')[0]))

# Automatically detect deployments to other app ids
if _APP_ID not in _APP_IDS:
  PLAYGROUND_APP_ID = _APP_ID
  EXEC_CODE_APP_ID = _APP_ID
TWO_COLLABORATING_APP_IDS = PLAYGROUND_APP_ID != EXEC_CODE_APP_ID

if _DEV_MODE:
  PLAYGROUND_HOSTS = ('localhost:8080', '127.0.0.1:8080',
                      # port 7070 for karma e2e test
                      'localhost:7070', '127.0.0.1:7070',
                      app_identity.get_default_version_hostname())
  # PLAYGROUND_USER_CONTENT_HOST = backends.get_hostname('user-content-backend')
  PLAYGROUND_USER_CONTENT_HOST = None
  EXEC_CODE_HOST = backends.get_hostname('exec-code-backend')
else:
  PLAYGROUND_HOSTS = ('{}.appspot.com'.format(PLAYGROUND_APP_ID),
                      '{}.appspot.com'.format(PLAYGROUND_APP_ID_ALIAS))
  # PLAYGROUND_USER_CONTENT_HOST = ('{0}-dot-{1}.appspot.com'
  #                                 .format(USER_CONTENT_PREFIX,
  #                                         PLAYGROUND_APP_ID))
  PLAYGROUND_USER_CONTENT_HOST = None
  EXEC_CODE_HOST = '{0}.appspot.com'.format(EXEC_CODE_APP_ID)


def PrintAppIdsInMap():
  """Prints a new line delimited list of known app ids."""
  print '\n'.join(_APP_IDS)
