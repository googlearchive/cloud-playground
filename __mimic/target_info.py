#!/usr/bin/env python
#
# Copyright 2012 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Module for processing target application related information."""



import re

# TODO: Lots of app.yaml functionality is still missing.


# constants for login attribute
LOGIN_NONE = 0
LOGIN_REQUIRED = 1
LOGIN_ADMIN = 2

# mapping from yaml values to login constants
_LOGIN_VALUE_MAP = {
    None: LOGIN_NONE,
    'required': LOGIN_REQUIRED,
    'admin': LOGIN_ADMIN,
}

# constants for secure attribute
SECURE_NONE = 0
SECURE_OPTIONAL = 1
SECURE_NEVER = 2
SECURE_ALWAYS = 3

# mapping from yaml values to login constants
_SECURE_VALUE_MAP = {
    None: SECURE_NONE,
    'optional': SECURE_OPTIONAL,
    'never': SECURE_NEVER,
    'always': SECURE_ALWAYS,
}

# These inbound services are included in mimic's app.yaml and are always
# available, regardless of the target's app.yaml file. However, it is
# important to allow them in the app.yaml file in the event that the developer
# want to enable the inbound service in production.
# TODO: actually implement handing and routing of these services
_SUPPORTED_INBOUND_SERVICES = set(['channel_presence', 'mail', 'xmpp_message',
                                   'xmpp_presence', 'xmpp_subscribe', 'warmup'])

# These builtins are included in mimic's app.yaml and are always available,
# regardless of the target's app.yaml file.  However it is important to allow
# them in the app.yaml file in the event that the developer wants to enable
# the builtin in production.
_SUPPORTED_BUILTINS = set(['appstats', 'datastore_admin', 'deferred',
                           'remote_api'])

# These libraries are included in mimic's app.yaml and are always available,
# regardless of the target's app.yaml file.  However it is important to allow
# them in the app.yaml file in the event that the developer wants to enable
# the library in production. See google/appengine/api/appinfo.py
_SUPPORTED_LIBRARIES = set(['django', 'jinja2', 'lxml', 'markupsafe', 'numpy',
                            'PIL', 'pycrypto', 'setuptools', 'webapp2', 'webob',
                            'yaml'])

# Regular expression for matching cache expiration deltas.
# Lifted from google/appengine/api/appinfo.py
_DELTA_REGEX = r'([0-9]+)([DdHhMm]|[sS]?)'
_EXPIRATION_REGEX = r'^\s*(%s)(\s+%s)*\s*$' % (_DELTA_REGEX, _DELTA_REGEX)

# Match default expiration time for static resources as documented in:
# https://developers.google.com/appengine/docs/python/config/appconfig
_DEFAULT_STATIC_FILE_EXPIRATION = '10m'


class ValidationError(Exception):
  """An error signalling a problem in app.yaml data."""
  pass

  # TODO: It would be nice if ValidationErrors provided more context
  # to help developers fix the problem in their app.yaml file.


class Page(object):
  """A base class for the result of matching a path to an application config.

  It is assumed that subclasses will be plain-old-data objects that assign
  values to specific attributes.  The base class exists to provide attributes
  common to all pages, and to provide convenient implementations of __hash__,
  __eq__, and __ne__ to make testing easier.

  Attributes:
    login: One of the login constants (e.g. LOGIN_REQUIRED)
    secure: One of the secure constants (e.g. SECURE_ALWAYS)
  """

  def __init__(self, login, secure):
    """Initialize with the specified login value."""
    self.login = login
    self.secure = secure

  def __hash__(self):
    return hash(self.__dict__)

  def __eq__(self, other):
    return (type(self) == type(other) and
            self.__dict__ == other.__dict__)

  def __ne__(self, other):
    return not self == other


class StaticPage(Page):
  """The result of a static page match.

  Attributes:
    file_path: The full path of the file to be served.
    login: One of the login constants (e.g. LOGIN_REQUIRED)
    secure: One of the secure constants (e.g. SECURE_ALWAYS)
    mime_type: A MIME type to serve this page as (optional).
  """

  def __init__(self, file_path, expiration=_DEFAULT_STATIC_FILE_EXPIRATION,
               login=LOGIN_NONE, secure=SECURE_NONE, mime_type=None):
    Page.__init__(self, login, secure)
    self.file_path = file_path
    self.mime_type = mime_type
    self.expiration = expiration

  def __repr__(self):
    return ('<StaticPage file_path={0!r} mime_type={1!r} '
            'expiration={2!r}>'.format(self.file_path, self.mime_type,
                                       self.expiration))


class ScriptPage(Page):
  """The result of a script page match.

  Attributes:
    script_path: The full path of the script.
    login: One of the login constants (e.g. LOGIN_REQUIRED)
    secure: One of the secure constants (e.g. SECURE_ALWAYS)
  """

  def __init__(self, script_path, login=LOGIN_NONE, secure=SECURE_NONE):
    Page.__init__(self, login, secure)
    self.script_path = script_path

  def __repr__(self):
    return '<ScriptPage %s>' % self.script_path


class _Checker(object):
  """A helper object for checking configuration dictionaries.

  Typical usage:
    checker = _Checker(config)
    foo = checker.Get('foo')
    # do something specific with foo
    # ...
    checker.IsAtom('bar')  # verify that bar is a string or int
    # ...
    checker.NoUnchecked()  # verify that no unchecked fields remain
  """

  def __init__(self, mapping):
    """Initialize a checker from a dictionary."""
    self._mapping = mapping
    self._unchecked = set(mapping.keys())

  def Get(self, name, optional=False):
    """Get a field's value.

    Args:
      name: The name of the field.
      optional: Determines what happens when a field is not present.  If True,
        then None is returned.  If False, a ValidationError is raised.

    Returns:
      The field's value or None.

    Raises:
      ValidationError: If the field is not present and optional is False.
    """
    self._unchecked.discard(name)
    value = self._mapping.get(name)
    if value is None and not optional:
      raise ValidationError('field {0!r} is required in app.yaml'.format(name))
    return value

  def Has(self, name):
    """Check if a field exists.

    Args:
      name: The name of the field.

    Returns:
      True if the field exists, False otherwise.
    """
    self._unchecked.discard(name)
    return name in self._mapping

  def RequireAtom(self, name):
    """Raises a ValidationError if the specified field is not an atom."""
    value = self.Get(name)
    if not isinstance(value, str) and not isinstance(value, int):
      raise ValidationError('field {0!r} is not a string or int in app.yaml'
                            .format(name))

  def RequireInteger(self, name):
    """Raises a ValidationError if the specified field is not an integer."""
    value = self.Get(name)
    if not isinstance(value, int):
      raise ValidationError('field {0!r} is not an integer in app.yaml'
                            .format(name))

  def NoUnchecked(self):
    """Raises a ValidationError if any unchecked fields remain."""
    if self._unchecked:
      fields = ', '.join(self._unchecked)
      raise ValidationError('unsupported fields {0!r} in app.yaml'
                            .format(fields))


def _ValidateExpiration(checker, field):
  """Validates the given expiration attribute given the field name.

  Args:
    checker: the checker to check the expiration field for
    field: the name of the expiration field (either 'expiration' or
        'default_expiration')

  Raises:
    ValidationError: If the expiration's value is not properly formatted.
  """
  expiration = checker.Get(field, optional=True)
  if not expiration:
    return
  if not re.match(_EXPIRATION_REGEX, expiration):
    raise ValidationError('invalid value {0!r} for {1!r} attribute in app.yaml'
                          .format(expiration, field))


def _ValidateSecure(checker):
  """Validates the given secure attribute.

  Args:
    checker: the checker to check the expiration field for

  Raises:
    ValidationError: If the secure's value is not one of ('optional', 'never',
                     'always').
  """
  secure = checker.Get('secure', optional=True)
  allowed_strings = [k for k in _SECURE_VALUE_MAP.keys() if k]
  if secure is None and checker.Has('secure'):
    raise ValidationError('secure attribute in app.yaml must be ommitted or be '
                          'one of {0!r}'.format(allowed_strings))
  if secure not in _SECURE_VALUE_MAP:
    raise ValidationError('invalid secure attribute value {0!r} not one of '
                          '{1!r} in app.yaml'.format(secure, allowed_strings))


def _ValidateHandler(handler, threadsafe):
  """Validate a handler.

  Args:
    handler: A handler dictionary (parsed from app.yaml).
    threadsafe: A bool indicating if this app is threadsafe. If threadsafe is
      true, then CGI handlers aren't supported.

  Raises:
    ValidationError: If any problems are detected in the config.
  """
  checker = _Checker(handler)
  checker.RequireAtom('url')
  login = checker.Get('login', optional=True)
  if login not in _LOGIN_VALUE_MAP:
    raise ValidationError('illegal value {0!r} for login attribute'
                          .format(login))
  _ValidateSecure(checker)
  if checker.Has('static_dir'):
    checker.RequireAtom('static_dir')
    if checker.Has('mime_type'):
      checker.RequireAtom('mime_type')
    _ValidateExpiration(checker, 'expiration')
  elif checker.Has('static_files'):
    checker.RequireAtom('static_files')
    checker.RequireAtom('upload')
    if checker.Has('mime_type'):
      checker.RequireAtom('mime_type')
    _ValidateExpiration(checker, 'expiration')
  elif checker.Has('script'):
    script = checker.Get('script')
    is_cgi = script.endswith('.py') or '/' in script
    if threadsafe and is_cgi:
      raise ValidationError('threadsafe cannot be enabled with CGI handlers: '
                            '{0!r}. All handlers must be WSGI handlers.'
                            .format(script))
    # This catches script handlers like "foo" or "module", which aren't valid
    # (Note that "foo/" is valid). Also assume anything with a regex
    # backreference ("\n") is ok, because it's difficult to know what that ends
    # up being.
    if not (is_cgi or '.' in script or '\\' in script):
      raise ValidationError('invalid script handler: {0!r}'.format(script))
  else:
    raise ValidationError('unsupported handler type {0!r}'.format(handler))
  checker.NoUnchecked()


def _ValidateInboundService(service):
  """Validate a service.

  Args:
    service: A service dictionary (parsed from app.yaml).

  Raises:
    ValidationError: If the service is not supported or misconfigured.
  """
  if not isinstance(service, str):
    raise ValidationError('inbound service {0!r} must be a single field'
                          .format(service))
  if service not in _SUPPORTED_INBOUND_SERVICES:
    raise ValidationError('{0!r} is not among supported inbound_services {1!r} '
                          'in app.yaml'.format(service,
                                               _SUPPORTED_INBOUND_SERVICES))


def _ValidateBuiltin(builtin):
  """Validate a builtin.

  Args:
    builtin: A builtin dictionary (parsed from app.yaml).

  Raises:
    ValidationError: If the builtin is not supported or misconfigured.
  """
  if not isinstance(builtin, dict) or len(builtin) != 1:
    raise ValidationError('Each builtin must be a single key/value pair')
  name = builtin.keys()[0]
  value = builtin[name]
  if name not in _SUPPORTED_BUILTINS:
    raise ValidationError('builtin {0!r} is not among supported builtins {1!r} '
                          'in app.yaml'.format(name, _SUPPORTED_BUILTINS))
  if value is not True:
    raise ValidationError('Builtin {0!r} must have a value of "on"'
                          .format(name))


def _ValidateLibrary(library):
  """Validate a library.

  Args:
    library: A library dictionary (parsed from app.yaml).

  Raises:
    ValidationError: If the library is not supported or misconfigured.
  """
  if not isinstance(library, dict) or len(library) != 2:
    raise ValidationError('app.yaml libraries must declare name and version')
  for key in ('name', 'version'):
    if key not in library:
      raise ValidationError('app.yaml libraries must declare a {0!r}'
                            .format(key))
  name = library.get('name')
  if name not in _SUPPORTED_LIBRARIES:
    raise ValidationError('app.yaml library {0!r} is not among supported '
                          'libraries {1!r}'.format(name, _SUPPORTED_LIBRARIES))
  version = library.get('version')
  # Keep in sync with our app.yaml which specifies 'latests' for all libraries.
  if version != 'latest':
    raise ValidationError('app.yaml library version must be {0!r}'
                          .format('latest'))


def _ValidateConfig(config):
  """Validate an application config.

  Args:
    config: An application config dictionary (parsed from app.yaml).

  Raises:
    ValidationError: If any problems are detected in the config.
  """
  checker = _Checker(config)
  checker.RequireAtom('application')
  checker.RequireAtom('version')

  value = checker.Get('runtime')
  if value != 'python27':
    raise ValidationError('app.yaml must specify {0!r}'
                          .format('runtime: python27'))

  threadsafe = checker.Get('threadsafe')
  if not isinstance(threadsafe, bool):
    raise ValidationError('app.yaml must specify threadsafe true or false')

  value = checker.Get('api_version')
  if value != 1:
    raise ValidationError('app.yaml must specify api_version: 1')

  handlers = checker.Get('handlers')
  if not handlers:
    raise ValidationError('app.yaml must specify at least one handler')
  for h in handlers:
    _ValidateHandler(h, threadsafe)

  inbound_services = checker.Get('inbound_services', optional=True)
  if inbound_services:
    if not isinstance(inbound_services, list):
      raise ValidationError('app.yaml inbound_services may not be empty')
    for s in inbound_services:
      _ValidateInboundService(s)

  builtins = checker.Get('builtins', optional=True)
  if builtins:
    if not isinstance(builtins, list):
      raise ValidationError('app.yaml builtins may not be empty')
    for b in builtins:
      _ValidateBuiltin(b)

  libraries = checker.Get('libraries', optional=True)
  if libraries:
    if not isinstance(libraries, list):
      raise ValidationError('app.yaml libraries may not be empty')
    for library in libraries:
      _ValidateLibrary(library)

  _ValidateExpiration(checker, 'default_expiration')

  if checker.Has('skip_files'):
    skip_files = checker.Get('skip_files', optional=True)
    if skip_files is None:
      raise ValidationError('app.yaml skip_files may not be empty')
    else:
      if not isinstance(skip_files, list):
        raise ValidationError('app.yaml skip_files must be a list')
      for skip_file in skip_files:
        if not isinstance(skip_file, str):
          raise ValidationError('app.yaml skip_files entries must be strings')

  checker.NoUnchecked()


def _MatchScript(handler, path):
  """Match a path to a regular expression and return a ScriptPage.

  Args:
    handler: A handler dictionary with a script field.
    path: The path portion of the url.

  Returns:
    A ScriptPage object or None.
  """
  pattern = handler['url']
  if not pattern.endswith('$'):
    pattern += '$'
  match = re.match(pattern, path)
  if match:
    template = handler['script']
    return ScriptPage(match.expand(template),
                      login=_LOGIN_VALUE_MAP[handler.get('login')],
                      secure=_SECURE_VALUE_MAP[handler.get('secure')])
  else:
    return None


def _MatchStaticDir(handler, path):
  """Match a path to a static_dir handler and return a StaticPage.

  Args:
    handler: A handler dictionary with a static_dir field.
    path: The path portion of the url.

  Returns:
    A StaticPage object or None.
  """
  prefix = handler['url']
  if not prefix.endswith('/'):
    prefix += '/'
  if not path.startswith(prefix):
    return None
  static_dir = handler['static_dir']
  if not static_dir.endswith('/'):
    static_dir += '/'
  return StaticPage(static_dir + path[len(prefix):],
                    login=_LOGIN_VALUE_MAP[handler.get('login')],
                    secure=_SECURE_VALUE_MAP[handler.get('secure')],
                    mime_type=handler.get('mime_type'),
                    expiration=handler.get('expiration'))


def _MatchStaticFile(handler, path):
  """Match a path to a regular expression and return a StaticPage.

  Args:
    handler: A handler dictionary with a static_files field.
    path: The path portion of the url.

  Returns:
    A StaticPage object or None.
  """
  pattern = handler['url']
  if not pattern.endswith('$'):
    pattern += '$'
  match = re.match(pattern, path)
  if not match:
    return None
  template = handler['static_files']
  return StaticPage(match.expand(template),
                    login=_LOGIN_VALUE_MAP[handler.get('login')],
                    secure=_SECURE_VALUE_MAP[handler.get('secure')],
                    mime_type=handler.get('mime_type'),
                    expiration=handler.get('expiration'))


def _MatchHandler(handler, path):
  """Match a path to a handler.

  Args:
    handler: A handler dictionary.
    path: The path portion of the url.

  Returns:
    A Page object or None.
  """
  if 'static_dir' in handler:
    return _MatchStaticDir(handler, path)
  elif 'static_files' in handler:
    return _MatchStaticFile(handler, path)
  elif 'script' in handler:
    return _MatchScript(handler, path)
  else:
    # this should never happen on validated handlers
    assert False


def FindPage(config, path):
  """Return the Page resulting from matching path against a config.

  Args:
    config: The app config loaded from app.yaml.
    path: The path portion of the requested URL.

  Returns:
    A Page object representing the first matching handler, or None
    if no match is found.

  Raises:
    ValidationError: if the app_yaml data is invalid.
  """
  _ValidateConfig(config)
  default_expiration = config.get('default_expiration',
                                  _DEFAULT_STATIC_FILE_EXPIRATION)
  for handler in config['handlers']:
    # ensure handler has an explicit expiration
    handler.setdefault('expiration', default_expiration)
    page = _MatchHandler(handler, path)
    if page is not None:
      return page
  return None
