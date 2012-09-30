"""Module containing global bliss constants and functions."""

# namespace for bliss specific data
BLISS_NAMESPACE = '_bliss'

# Extensions to exclude when creating template projects
SKIP_EXTENSIONS = ('swp', 'pyc', 'svn')

# list of bliss tuples (<bliss app id>, <playground app id>)
_BLISS_TO_PLAYGROUND_DICT = {
    'try-appengine': 'shared-playground',
}
_PLAYGROUND_TO_BLISS_DICT = dict(
    (v, k) for k, v in _BLISS_TO_PLAYGROUND_DICT.iteritems())


def GetBlissAppIdFor(app_id):
  """Lookup the bliss app id for the provided app id.

  Args:
    app_id: The app id to to use as the lookup key or default.

  Returns:
    The bliss app id if known, else the provided the app id.
  """
  return _PLAYGROUND_TO_BLISS_DICT.get(app_id, app_id)


def GetPlaygroundAppIdFor(app_id):
  """Lookup the playground app id for the provided app id.

  Args:
    app_id: The app id to to use as the lookup key or default.

  Returns:
    The playground app id if known, else the provided the app id.
  """
  return _BLISS_TO_PLAYGROUND_DICT.get(app_id, app_id)


def GetBlissDefaultVersionHostname(app_id):
  """Return default bliss version hostname for the associated app id.

  Args:
    app_id: The app id to to use as the lookup key or default.

  Returns:
    The default version hostname for the bliss app id.
  """
  bliss_app_id = GetBlissAppIdFor(app_id)
  return '{0}.appspot.com'.format(bliss_app_id)


def GetPlaygroundDefaultVersionHostname(app_id):
  """Return default playground version hostname for the associated app id.

  Args:
    app_id: The app id to to use as the lookup key or default.

  Returns:
    The default version hostname for the playground app id.
  """
  playground_app_id = GetPlaygroundAppIdFor(app_id)
  return '{0}.appspot.com'.format(playground_app_id)


def PrintAppIdsInMap():
  """Prints a new line delimited list of known app ids."""
  app_ids = set(_BLISS_TO_PLAYGROUND_DICT.keys() +
      _BLISS_TO_PLAYGROUND_DICT.values())
  print '\n'.join(app_ids)
