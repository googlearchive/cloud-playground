import json


_JSON_ENCODER = json.JSONEncoder()
_JSON_ENCODER.indent = 4
_JSON_ENCODER.sort_keys = True

_JSON_DECODER = json.JSONDecoder()


JSON_MIME_TYPE = 'application/json'


def tojson(r):  # pylint:disable-msg=invalid-name
  """Converts a Python object to JSON."""
  return _JSON_ENCODER.encode(r)


def fromjson(json):  # pylint:disable-msg=invalid-name
  """Converts a JSON object into a Python object."""
  if json == '':
    return None
  return _JSON_DECODER.decode(json)

