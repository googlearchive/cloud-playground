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

"""Unit tests for target_info."""



from __mimic import target_info
import yaml

import unittest

# a basic config to use as the starting point for tests
APP_YAML = """
application: my_app
version: 1
runtime: python27
api_version: 1
threadsafe: true

handlers:
- url: /images
  static_dir: static/images
"""

VALID_SECURES = ['optional', 'never', 'always']

INVALID_SECURES = ['', 'http', 'https', 'ssl', 'OPTIONAL', 'NEVER', 'ALWAYS']

VALID_EXPIRATIONS = ['', '1d', '1d 2h 3m 4s', '1D 2H 3M 4S', '45']

INVALID_EXPIRATIONS = ['1z', '0.5d', '1d, 2h', '1hour', '1 hour']


class ValidateConfigTest(unittest.TestCase):
  """Tests for _ValidateConfig."""

  def CheckError(self, config):
    """Check that a ValidationError is raised when validating the config."""
    self.assertRaises(target_info.ValidationError,
                      target_info._ValidateConfig, config)

  def CheckField(self, name, bad_value):
    """Check that errors are raised when the field is missing or bad."""
    config = yaml.load(APP_YAML)
    del config[name]
    self.CheckError(config)
    config[name] = bad_value
    self.CheckError(config)

  # make sure that a valid config passes
  def testOk(self):
    target_info._ValidateConfig(yaml.load(APP_YAML))

  # test various bad/missing fields
  def testApplication(self):
    # lists are not valid application names
    self.CheckField('application', [1])

  def testVersion(self):
    # lists are not valid version numbers
    self.CheckField('version', [1])

  def testRuntime(self):
    # only python27 is supported
    self.CheckField('runtime', 'foo')

  def testThreadsafe(self):
    # only threadsafe is supported
    self.CheckField('threadsafe', 'foo')

  def testApiVersion(self):
    # only api_version 1 is supported
    self.CheckField('api_version', 2)

  def testUnknownField(self):
    config = yaml.load(APP_YAML)
    config['foo'] = 'bar'
    self.CheckError(config)

  def testNoHandlers(self):
    # empty list of handlers is not allowed
    self.CheckField('handlers', [])

  def testStaticFiles(self):
    config = yaml.load(APP_YAML)
    handler = {'url': '/x(.*)x', 'static_files': r'static/\1',
               'expiration': '10m'}
    config['handlers'] = [handler]
    self.CheckError(config)
    handler['upload'] = 'static/.*'
    target_info._ValidateConfig(config)

  def testCGIScript(self):
    config = yaml.load(APP_YAML)
    handler = {'url': '/', 'script': 'main.py'}
    config['handlers'] = [handler]
    # CGI handlers supported only when threadsafe is false
    config['threadsafe'] = False
    target_info._ValidateConfig(config)

  def testWSGIScript(self):
    config = yaml.load(APP_YAML)
    handler = {'url': '/', 'script': 'main.app'}
    config['handlers'] = [handler]
    target_info._ValidateConfig(config)

  def testCGIScriptRaisesValidationError(self):
    config = yaml.load(APP_YAML)
    handler = {'url': '/', 'script': 'main.py'}
    config['handlers'] = [handler]
    # CGI handlers aren't supported when threadsafe is true
    self.assertRaises(target_info.ValidationError, target_info._ValidateConfig,
                      config)

  def testCGIModuleValidation(self):
    config = yaml.load(APP_YAML)
    handler = {'url': '/', 'script': 'foo/bar'}
    config['handlers'] = [handler]
    # CGI handlers aren't supported when threadsafe is true
    self.assertRaises(target_info.ValidationError, target_info._ValidateConfig,
                      config)
    # should pass if threadsafe is false
    config['threadsafe'] = False
    target_info._ValidateConfig(config)

  def testTopLevelPackageRaisesValidationError(self):
    """A "top level" package is invalid (to match the dev_appserver)."""
    config = yaml.load(APP_YAML)
    handler = {'url': '/', 'script': 'foo'}
    config['handlers'] = [handler]
    # CGI handlers aren't supported when threadsafe is true
    self.assertRaises(target_info.ValidationError, target_info._ValidateConfig,
                      config)
    config['threadsafe'] = False
    self.assertRaises(target_info.ValidationError, target_info._ValidateConfig,
                      config)

  def testLogin(self):
    def Check(handler):
      config = yaml.load(APP_YAML)
      config['handlers'] = [handler]
      handler['login'] = 'required'
      target_info._ValidateConfig(config)
      handler['login'] = 'admin'
      target_info._ValidateConfig(config)
      handler['login'] = 'not-valid'
      self.assertRaises(target_info.ValidationError,
                        target_info._ValidateConfig, config)

    Check({'url': '/', 'script': 'main.app'})
    Check({'url': '/', 'static_files': 'index.html', 'upload': 'index.html'})
    Check({'url': '/', 'static_dir': 'static'})

  def testBuiltinNotList(self):
    config = yaml.load(APP_YAML + """
builtins: 123
""")
    self.assertRaises(target_info.ValidationError,
                      target_info._ValidateConfig, config)

  def testBuiltinNotWellFormed(self):
    config = yaml.load(APP_YAML + """
builtins:
- appstats: on
  remote_api: on
""")
    self.assertRaises(target_info.ValidationError,
                      target_info._ValidateConfig, config)

  def testBuiltinUndefined(self):
    config = yaml.load(APP_YAML + """
builtins:
- foo: on
""")
    self.assertRaises(target_info.ValidationError,
                      target_info._ValidateConfig, config)

  def testBuiltinBadValue(self):
    config = yaml.load(APP_YAML + """
builtins:
- appstats: 123
""")
    self.assertRaises(target_info.ValidationError,
                      target_info._ValidateConfig, config)

  def testBuiltinAppstats(self):
    config = yaml.load(APP_YAML + """
builtins:
- appstats: on
""")
    target_info._ValidateConfig(config)

  def testBuiltinDeferred(self):
    config = yaml.load(APP_YAML + """
builtins:
- deferred: on
""")
    target_info._ValidateConfig(config)

  def testBuiltinRemoteApi(self):
    config = yaml.load(APP_YAML + """
builtins:
- remote_api: on
""")
    target_info._ValidateConfig(config)

  def testBuiltinDatastoreAdmin(self):
    config = yaml.load(APP_YAML + """
builtins:
- datastore_admin: on
""")
    target_info._ValidateConfig(config)

  def testMimeTypeOnStaticDir(self):
    config = yaml.load(APP_YAML + """
  mime_type: text/plain
""")
    target_info._ValidateConfig(config)

  def testMimeTypeOnStaticFiles(self):
    config = yaml.load(APP_YAML)
    handler = {'url': '/x(.*)x', 'static_files': r'static/\1',
               'upload': 'static/.*', 'mime_type': 'image/gif',
               'expiration': '10m'}
    config['handlers'] = [handler]
    target_info._ValidateConfig(config)

  def testMimeTypeOnScript(self):
    config = yaml.load(APP_YAML)
    handler = {'url': '/', 'script': 'main.py', 'mime_type': 'text/plain'}
    config['handlers'] = [handler]
    self.assertRaises(target_info.ValidationError,
                      target_info._ValidateConfig, config)

  def testMimeTypeNotAtom(self):
    config = yaml.load(APP_YAML + """
  mime_type:
    - foo: bar
    - baz: flux
""")
    self.assertRaises(target_info.ValidationError,
                      target_info._ValidateConfig, config)

  def testHandlerExpiration(self):
    config = yaml.load(APP_YAML)
    config['handlers'].append({
        'url': '/x(.*)x',
        'static_files': r'static/\1',
        'upload': 'static/.*'
    })
    for value in VALID_EXPIRATIONS:
      for config_handler in config['handlers']:
        config_handler['expiration'] = value
      # should pass
      target_info._ValidateConfig(config)

  def testHandlerBadExpirationStaticDir(self):
    config = yaml.load(APP_YAML)
    for value in INVALID_EXPIRATIONS:
      config['handlers'][0]['expiration'] = value
      # shouldn't pass
      self.CheckError(config)

  def testHandlerBadExpirationStaticFiles(self):
    config = yaml.load(APP_YAML)
    config['handlers'] = [{
        'url': '/x(.*)x',
        'static_files': r'static/\1',
        'upload': 'static/.*'
    }]
    for value in INVALID_EXPIRATIONS:
      config['handlers'][0]['expiration'] = value
      # shouldn't pass
      self.CheckError(config)

  def testScriptHandlerExpiration(self):
    config = yaml.load(APP_YAML)
    config['handlers'] = [{
        'url': '/',
        'script': 'main.py',
        'expiration': '1d'
    }]
    # script handlers don't have expirations
    self.CheckError(config)

  def testDefaultExpiration(self):
    config = yaml.load(APP_YAML)
    for value in VALID_EXPIRATIONS:
      config['default_expiration'] = value
      # should pass
      target_info._ValidateConfig(config)

  def testBadDefaultExpiration(self):
    config = yaml.load(APP_YAML)
    for value in INVALID_EXPIRATIONS:
      config['default_expiration'] = value
      # shouldn't pass
      self.CheckError(config)

  def testHandlerSecure(self):
    config = yaml.load(APP_YAML)
    config['handlers'].extend([{
        'url': '/x(.*)x',
        'static_files': r'static/\1',
        'upload': 'static/.*'
    },{
        'url': '/y(.*)y',
        'script': 'y.app',
    }])
    for value in VALID_SECURES:
      for config_handler in config['handlers']:
        config_handler['secure'] = value
      # should pass
      target_info._ValidateConfig(config)

  def testHandlerBadSecureStaticDir(self):
    config = yaml.load(APP_YAML)
    for value in INVALID_SECURES:
      config['handlers'][0]['secure'] = value
      # shouldn't pass
      self.CheckError(config)

  def testHandlerBadSecureStaticFiles(self):
    config = yaml.load(APP_YAML)
    config['handlers'] = [{
        'url': '/x(.*)x',
        'static_files': r'static/\1',
        'upload': 'static/.*'
    }]
    for value in INVALID_SECURES:
      for config_handler in config['handlers']:
        config_handler['secure'] = value
      # shouldn't pass
      self.CheckError(config)

  def testHandlerBadSecureScript(self):
    config = yaml.load(APP_YAML)
    config['handlers'] = [{
        'url': '/y(.*)y',
        'script': 'y.app',
    }]
    for value in INVALID_SECURES:
      config['handlers'][0]['secure'] = value
      # shouldn't pass
      self.CheckError(config)

  def testSkipFiles(self):
    config = yaml.load(APP_YAML + """
skip_files:
- ^(.*/)?skip_folder.*
- ^(.*/)?README\.txt
""")
    target_info._ValidateConfig(config)

  def testEmptySkipFiles(self):
    config = yaml.load(APP_YAML + """
skip_files:
""")
    self.assertRaises(target_info.ValidationError, target_info._ValidateConfig,
                      config)

  def testBadSkipFiles(self):
    config = yaml.load(APP_YAML + """
skip_files:
- foo: bar
  baz: potato
""")
    self.assertRaises(target_info.ValidationError, target_info._ValidateConfig,
                      config)


class MatchHandlerTest(unittest.TestCase):
  """Tests for _MatchHandler and its helper functions."""

  def testStaticDir(self):
    def CheckHandler(url, static_dir):
      handler = {'url': url, 'static_dir': static_dir, 'expiration': '10m'}
      self.assertEquals(target_info.StaticPage('bar/x.html'),
                        target_info._MatchHandler(handler, '/foo/x.html'))
      self.assertIsNone(target_info._MatchHandler(handler, '/notfoo/x.html'))
      self.assertIsNone(target_info._MatchHandler(handler, '/foox.html'))
    # Trailing slashes are optional on both the url and static_dir, but
    # a directory is implied regardless.
    CheckHandler('/foo', 'bar')
    CheckHandler('/foo', 'bar/')
    CheckHandler('/foo/', 'bar')
    CheckHandler('/foo/', 'bar/')

  def testStaticFiles(self):
    handler = {'url': '/x(.*)x', 'static_files': r'static/\1',
               'expiration': '10m'}
    self.assertEquals(target_info.StaticPage('static/foo'),
                      target_info._MatchHandler(handler, '/xfoox'))
    self.assertIsNone(target_info._MatchHandler(handler, '/abc'))

  def testScript(self):
    handler = {'url': '/x(.*)x', 'script': r'\1.py'}
    self.assertEquals(target_info.ScriptPage('foo.py'),
                      target_info._MatchHandler(handler, '/xfoox'))
    self.assertIsNone(target_info._MatchHandler(handler, '/abc'))

  def testLogin(self):
    def Check(handler):
      page = target_info._MatchHandler(handler, '/')
      self.assertEquals(target_info.LOGIN_NONE, page.login)
      handler['login'] = 'required'
      page = target_info._MatchHandler(handler, '/')
      self.assertEquals(target_info.LOGIN_REQUIRED, page.login)
      handler['login'] = 'admin'
      page = target_info._MatchHandler(handler, '/')
      self.assertEquals(target_info.LOGIN_ADMIN, page.login)

    Check({'url': '/', 'script': 'foo.py'})
    Check({'url': '/', 'static_dir': 'static'})
    Check({'url': '/', 'static_files': 'index.html'})

  def testStaticDirMimeType(self):
    def CheckMimeType(mime_type):
      handler = {'url': '/foo', 'static_dir': 'bar', 'expiration': '10m'}
      if mime_type is not None:
        handler['mime_type'] = mime_type
      self.assertEquals(target_info.StaticPage('bar/x.html',
                                               mime_type=mime_type),
                        target_info._MatchHandler(handler, '/foo/x.html'))

    CheckMimeType(None)
    CheckMimeType('text/plain')
    CheckMimeType('blah blah blah')

  def testStaticFilesMimeType(self):
    def CheckMimeType(mime_type):
      handler = {'url': '/x(.*)', 'static_files': r'static/\1',
                 'expiration': '10m'}
      if mime_type is not None:
        handler['mime_type'] = mime_type
      self.assertEquals(target_info.StaticPage('static/foo.xyz',
                                               mime_type=mime_type),
                        target_info._MatchHandler(handler, '/xfoo.xyz'))

    CheckMimeType(None)
    CheckMimeType('text/plain')
    CheckMimeType('text/html')
    CheckMimeType('blah blah blah')


class FindPageTest(unittest.TestCase):
  """Tests for FindPage."""

  def testMatch(self):
    config = yaml.load(APP_YAML)
    self.assertEquals(target_info.StaticPage('static/images/foo.png'),
                      target_info.FindPage(config, '/images/foo.png'))

  def testSecondMatch(self):
    app_yaml = APP_YAML + """
- url: /foo
  static_dir: bar
"""
    config = yaml.load(app_yaml)
    self.assertEquals(target_info.StaticPage('bar/x'),
                      target_info.FindPage(config, '/foo/x'))

  def testNoMatch(self):
    config = yaml.load(APP_YAML)
    self.assertIsNone(target_info.FindPage(config, '/foo.html'))

  def testInvalidConfig(self):
    app_yaml = APP_YAML + '\ninvalid_field: foo\n'
    config = yaml.load(app_yaml)
    self.assertRaises(target_info.ValidationError,
                      target_info.FindPage, config, '/index.html')


if __name__ == '__main__':
  unittest.main()
