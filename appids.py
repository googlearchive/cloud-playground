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

# All app ids used by this project
_APP_IDS = set((PLAYGROUND_APP_ID, MIMIC_APP_ID))

# Our app id
_APP_ID = os.environ['APPLICATION_ID'].split('~')[-1]
# support regular 'appspot.com' app ids only
assert ':' not in _APP_ID, ('{} app ids are unsupported'
                            .format(_APP_ID.split(':')[0]))

# Automatically detect deployments to other app ids
if _APP_ID not in _APP_IDS:
  PLAYGROUND_APP_ID = _APP_ID
  MIMIC_APP_ID = _APP_ID
TWO_COLLABORATING_APP_IDS = PLAYGROUND_APP_ID != MIMIC_APP_ID


def PrintAppIds():
  """Prints a new line delimited list of known app ids."""
  print '\n'.join((PLAYGROUND_APP_ID, MIMIC_APP_ID))
