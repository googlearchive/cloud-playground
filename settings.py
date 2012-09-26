# map app ids where user code is executed to app id where bliss runs
_APP_ID_MAP = {
  'shared-playground': 'try-appengine',
}

def GetBlissAppIdFor(app_id):
  """Lookup the Bliss app id for the provided app id.

  Returns:
    The Bliss app id if known, else the provided the app id.
  """
  return _APP_ID_MAP.get(app_id, app_id)

def PrintAppIdsInMap():
  """Prints a new line delimited list of known app ids."""
  app_ids = set(_APP_ID_MAP.keys() + _APP_ID_MAP.values())
  print '\n'.join(app_ids)
