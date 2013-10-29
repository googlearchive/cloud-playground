"""Module which defines collaborating app ids.

This module is used by:
  settings.py
  scripts/deploy.sh
"""


import os


# List of (playground appid, mimic app id, playground app id alias)
_APP_ID_TUPLES = [
    # production environment
    ('try-appengine', 'shared-playground', 'cloud-playground'),
    # development environment
    ('fredsa-bliss', 'fredsa-hr', None),
]


def _GetTupleFor(app_id):
  for app_ids in _APP_ID_TUPLES:
    if app_id in app_ids:
      return app_ids
  return (app_id, app_id, None)

# Our app id
_APP_ID = os.environ['APPLICATION_ID'].split('~')[-1]
# support regular 'appspot.com' app ids only
assert ':' not in _APP_ID, ('{} app ids are unsupported'
                            .format(_APP_ID.split(':')[0]))

app_ids = _GetTupleFor(_APP_ID)

# The application where the playground IDE runs
PLAYGROUND_APP_ID = app_ids[0]

# The application where user code runs
MIMIC_APP_ID = app_ids[1]

# The application alias where the playground IDE runs
PLAYGROUND_APP_ID_ALIAS = app_ids[2]

# Whether we're using two collaborating app ids
TWO_COLLABORATING_APP_IDS = PLAYGROUND_APP_ID != MIMIC_APP_ID


def PrintAppIds():
  """Prints a new line delimited list of known app ids."""
  print '\n'.join(set((PLAYGROUND_APP_ID, MIMIC_APP_ID)))
