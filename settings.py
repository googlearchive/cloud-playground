"""Module containing global bliss constants and functions."""

import os


# whether or not we're running in the dev_appserver
_DEV_MODE = os.environ['SERVER_SOFTWARE'].startswith('Development/')

# namespace for bliss specific data
BLISS_NAMESPACE = '_bliss'

# Extensions to exclude when creating template projects
SKIP_EXTENSIONS = ('swp', 'pyc', 'svn')

# The application where the bliss IDE runs
BLISS_APP_ID = 'try-appengine'

# The application where user code runs
PLAYGROUND_APP_ID = 'shared-playground'

USER_CONTENT_PREFIX = 'user-content'

# All app ids used by this project
_APP_IDS = (BLISS_APP_ID, PLAYGROUND_APP_ID)

if _DEV_MODE:
  BLISS_HOSTS = ('localhost:8080', '127.0.0.1:8080')
  BLISS_USER_CONTENT_HOST = 'localhost:9100'
  PLAYGROUND_HOST = 'localhost:9200'
else:
  BLISS_HOSTS = ('{0}.appspot.com'.format(BLISS_APP_ID),
                 'cloud-playground.appspot.com')
  BLISS_USER_CONTENT_HOST = ('{0}-dot-{1}.appspot.com'
                             .format(USER_CONTENT_PREFIX, BLISS_APP_ID))
  PLAYGROUND_HOST = '{0}.appspot.com'.format(PLAYGROUND_APP_ID)


def PrintAppIdsInMap():
  """Prints a new line delimited list of known app ids."""
  app_ids = set((BLISS_APP_ID, PLAYGROUND_APP_ID))
  print '\n'.join(app_ids)
