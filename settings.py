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


def GetBlissDefaultVersionHostname(app_id):
  """Return default version hostname for the associated bliss app id.

  Returns:
    The default version hostname for the bliss app id associated with this app,
    else the default version hostname for the provided app id.
  """
  bliss_app_id = GetBlissAppIdFor(app_id)
  return '{0}.appspot.com'.format(bliss_app_id)


def PrintAppIdsInMap():
  """Prints a new line delimited list of known app ids."""
  app_ids = set(_APP_ID_MAP.keys() + _APP_ID_MAP.values())
  print '\n'.join(app_ids)
