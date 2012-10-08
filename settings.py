"""Module containing global bliss constants and functions."""

# namespace for bliss specific data
BLISS_NAMESPACE = '_bliss'

# Extensions to exclude when creating template projects
SKIP_EXTENSIONS = ('swp', 'pyc', 'svn')

# The application where the bliss IDE runs
BLISS_APP_ID = 'try-appengine'

# An application id alias for the bliss IDE which can safely serve user content
BLISS_ALIAS_APP_ID = 'try-appengine-user-content'

# The application where user code runs
PLAYGROUND_APP_ID = 'shared-playground'

# All app ids used by this project
_APP_IDS = (BLISS_APP_ID, PLAYGROUND_APP_ID)

BLISS_HOST = '{0}.appspot.com'.format(BLISS_APP_ID)

BLISS_USER_CONTENT_HOST = '{0}.appspot.com'.format(BLISS_ALIAS_APP_ID)

PLAYGROUND_HOST = '{0}.appspot.com'.format(PLAYGROUND_APP_ID)


def PrintAppIdsInMap():
  """Prints a new line delimited list of known app ids."""
  app_ids = set((BLISS_APP_ID, PLAYGROUND_APP_ID))
  print '\n'.join(app_ids)
