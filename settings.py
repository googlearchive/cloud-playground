"""Module containing global playground constants and functions."""

import os

from google.appengine.api import app_identity
from google.appengine.api import backends


# whether or not we're running in the dev_appserver
_DEV_MODE = os.environ['SERVER_SOFTWARE'].startswith('Development/')

# namespace for playground specific data
PLAYGROUND_NAMESPACE = '_playground'

# template projects location
TEMPLATE_PROJECT_DIR = 'repos/'

# Extensions to exclude when creating template projects
SKIP_EXTENSIONS = ('swp', 'pyc', 'svn')

# The application where the playground IDE runs
PLAYGROUND_APP_ID = 'try-appengine'

# The application where user code runs
EXEC_CODE_APP_ID = 'shared-playground'

USER_CONTENT_PREFIX = 'user-content'

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

if _DEV_MODE:
  PLAYGROUND_HOSTS = ('localhost:8080', '127.0.0.1:8080',
                      # port 7070 for karma e2e test
                      'localhost:7070', '127.0.0.1:7070',
                      app_identity.get_default_version_hostname())
  PLAYGROUND_USER_CONTENT_HOST = backends.get_hostname('devappserver-cors-test')
  EXEC_CODE_HOST = backends.get_hostname('devappserver-playground-test')
else:
  PLAYGROUND_HOSTS = ('{0}.appspot.com'.format(PLAYGROUND_APP_ID),
                      'cloud-playground.appspot.com')
  PLAYGROUND_USER_CONTENT_HOST = ('{0}-dot-{1}.appspot.com'
                                  .format(USER_CONTENT_PREFIX,
                                          PLAYGROUND_APP_ID))
  EXEC_CODE_HOST = '{0}.appspot.com'.format(EXEC_CODE_APP_ID)


def PrintAppIdsInMap():
  """Prints a new line delimited list of known app ids."""
  print '\n'.join(_APP_IDS)
