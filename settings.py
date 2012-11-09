"""Module containing global playground constants and functions."""

import os


# whether or not we're running in the dev_appserver
_DEV_MODE = os.environ['SERVER_SOFTWARE'].startswith('Development/')

# namespace for playground specific data
PLAYGROUND_NAMESPACE = '_playground'

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

# Automatically detect deployments to other app ids
if _APP_ID not in _APP_IDS:
  PLAYGROUND_APP_ID = _APP_ID
  EXEC_CODE_APP_ID = _APP_ID

if _DEV_MODE:
  PLAYGROUND_HOSTS = ('localhost:8080', '127.0.0.1:8080')
  PLAYGROUND_USER_CONTENT_HOST = 'localhost:9100'
  EXEC_CODE_HOST = 'localhost:9200'
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
