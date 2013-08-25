"""Module which defines collaborating app ids.

This module is used by:
  settings.py
  scripts/deploy.sh
"""


# The application where the playground IDE runs
PLAYGROUND_APP_ID = 'try-appengine'

# The application where user code runs
MIMIC_APP_ID = 'shared-playground'

# The application alias where the playground IDE runs
PLAYGROUND_APP_ID_ALIAS = 'cloud-playground'


def PrintAppIds():
  """Prints a new line delimited list of known app ids."""
  print '\n'.join((PLAYGROUND_APP_ID, MIMIC_APP_ID))
