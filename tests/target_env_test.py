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
"""Unit tests for target_env."""



import encodings
import errno
import logging
import os
import re
import shutil
import sys
import tempfile
import time


# Import test_util first, to ensure python27 / webapp2 are setup correctly
from tests import test_util  # pylint: disable-msg=C6203

from __mimic import datastore_tree  # pylint: disable-msg=C6203
from __mimic import target_env
from __mimic import target_info
from tests import testpackage
import yaml

from google.appengine.api import files
from google.appengine.api import namespace_manager
from google.appengine.ext import blobstore

import unittest

# this will be set during test case setUp
_test_portal = None

_PEP302_ATTRIBUTE_SCRIPT = """
for attr in ('__file__', '__name__', '__path__', '__loader__'):
  setattr(_test_portal, attr, globals().get(attr, None))
"""

_TEST_CONFIG = yaml.load(r"""
handlers:
- url: /stylesheets
  static_dir: stylesheets

- url: /(.*\.(gif|png|jpg|html))
  static_files: static/\1
  upload: static/(.*\.(gif|png|jpg|html))

- url: /main
  script: main.py

skip_files:
- ^(.*/)?skip_folder.*
- ^(.*/)?README\.txt
""")


class TestPortal(object):
  """A trivial class that lets target code exchange data with the test."""
  pass


class CollectingHandler(logging.Handler):
  """A logging handler that saves all emitted records."""

  def __init__(self):
    logging.Handler.__init__(self)
    self.records = []

  def emit(self, record):
    self.records.append(record)


class TargetEnvironmentTest(unittest.TestCase):
  """Unit tests for TargetEnvironment."""

  def setUp(self):
    global _test_portal  # pylint: disable-msg=W0603
    _test_portal = TestPortal()
    test_util.InitAppHostingApi()
    namespace = 'project-name'
    self._tree = datastore_tree.DatastoreTree(namespace)
    self._env = target_env.TargetEnvironment(
        self._tree,
        _TEST_CONFIG,
        namespace,
        test_portal=_test_portal)
    # force loading of namespace_manager before target environment is
    # setup, so that we avoid recursion in tests trying to access the tree
    namespace_manager.get_namespace()
    self._env._SetUp()

  def tearDown(self):
    self._env._TearDown()

  def testInstance(self):
    self.assertTrue(self._env is target_env.TargetEnvironment.Instance())
    self._env._TearDown()
    self.assertIsNone(target_env.TargetEnvironment.Instance())

  def testSingleImport(self):
    self._tree.SetFile('foo.py', 'x = 123')
    import foo  # pylint: disable-msg=C6204, W0612
    self.assertEquals(sys.modules['foo'], foo)
    self.assertEquals(123, foo.x)
    self.assertEquals('/target/foo.py', foo.__file__)
    self.assertEquals('foo', foo.__name__)

  def testPackageImport(self):
    self._tree.SetFile('foo/__init__.py', 'x = 123')
    import foo  # pylint: disable-msg=C6204, W0612
    self.assertEquals(sys.modules['foo'], foo)
    self.assertEquals(123, foo.x)
    self.assertEquals('/target/foo/__init__.py', foo.__file__)
    self.assertEquals('foo', foo.__name__)

  def testSubModuleImport(self):
    self._tree.SetFile('foo/__init__.py', 'x = 123')
    self._tree.SetFile('foo/bar.py', 'y = 456')
    import foo.bar  # pylint: disable-msg=C6204, W0612
    self.assertEquals(sys.modules['foo.bar'], foo.bar)
    self.assertEquals(123, foo.x)
    self.assertEquals('/target/foo/__init__.py', foo.__file__)
    self.assertEquals('foo', foo.__name__)
    self.assertEquals(456, foo.bar.y)
    self.assertEquals('/target/foo/bar.py', foo.bar.__file__)
    self.assertEquals('foo.bar', foo.bar.__name__)

  def testModuleCleanup(self):
    self._tree.SetFile('foo.py', 'x = 123')
    import foo  # pylint: disable-msg=C6204, W0612
    self.assertTrue('foo' in sys.modules)
    self._env._TearDown()
    # foo should have been removed from sys.modules
    self.assertFalse('foo' in sys.modules)
    # import of foo without an installed TargetEnvironment
    try:
      import foo  # pylint: disable-msg=C6204, W0612, W0404
      self.fail()
    except ImportError:
      pass  # expected

  def testPackageCleanup(self):
    # pylint: disable-msg=C6204, W0404
    from tests.testpackage import testmodule
    self.assertEquals(123, testmodule.FOO)
    # modify state in testmodule
    testmodule.FOO = 456
    self.assertEquals(456, testmodule.FOO)
    # check that package and module both exist in sys.modules
    package_name = 'tests.testpackage'
    module_name = package_name + '.testmodule'
    self.assertTrue(package_name in sys.modules)
    self.assertTrue(module_name in sys.modules)
    self.assertTrue(hasattr(testpackage, 'testmodule'))
    # after TearDown, package should exist and module shouldn't
    self._env._TearDown()
    self.assertTrue(package_name in sys.modules)
    self.assertFalse(module_name in sys.modules)
    self.assertFalse(hasattr(testpackage, 'testmodule'))
    # run again, make sure module is imported cleanly with initial state
    self._env._SetUp()
    from tests.testpackage import testmodule
    self.assertEquals(123, testmodule.FOO)

  def testEncodingsAfterCleanup(self):
    # test that newly loaded encodings aren't cleaned up since that would
    # cause problems later
    encoding = 'mac_roman'
    module = 'encodings.%s' % encoding
    self.assertFalse(hasattr(encodings, encoding))
    self.assertFalse(module in sys.modules)
    # use the encoding
    'foo'.decode(encoding)
    # verify that the module exists
    self.assertTrue(hasattr(encodings, encoding))
    self.assertTrue(module in sys.modules)
    self._env._TearDown()
    # verify that cleanup doesn't get rid of the module and that encoding works
    self.assertTrue(hasattr(encodings, encoding))
    self.assertTrue(module in sys.modules)
    'foo'.decode(encoding)
    # verify that encodings continue to work after another SetUp
    self._env._SetUp()
    self.assertTrue(hasattr(encodings, encoding))
    self.assertTrue(module in sys.modules)
    'foo'.decode(encoding)

  def testErrorInModule(self):
    # This is a tricky test... we need to make sure that a module is installed
    # in sys.modules while it is loading, but that it then gets properly removed
    # if an Exception was raised.
    self._tree.SetFile('foo.py', """
import sys
_test_portal.foo_in_modules = 'foo' in sys.modules
y = 1 / 0  # will cause a ZeroDivisionError
""")
    try:
      import foo  # pylint: disable-msg=C6204, W0612
      self.fail()
    except ZeroDivisionError:
      pass  # expected
    self.assertTrue(_test_portal.foo_in_modules)
    self.assertFalse('foo' in sys.modules)

  def testImportPackageInsidePackage(self):
    self._env._TearDown()  # RunScript will set up the env
    self._tree.SetFile('main.py', """
_test_portal.files.append(__file__)
# spam will in turn import eggs which should be 'spam.eggs', not 'eggs'
import spam
# confirm that there is indeed a top level 'eggs'
# without this, the 'import eggs' test in spam would be incomplete
import eggs
""")
    self._tree.SetFile('spam/__init__.py', """
_test_portal.files.append(__file__)
# should import eggs from spam
import eggs
""")
    self._tree.SetFile('spam/eggs/__init__.py', """
_test_portal.files.append(__file__)
""")
    self._tree.SetFile('eggs/__init__.py', """
_test_portal.files.append(__file__)
""")
    _test_portal.files = []
    self._env.RunScript('main.py', CollectingHandler())
    self.assertEquals(['/target/main.py',
                       # 'import spam' in main.py
                       '/target/spam/__init__.py',
                       # 'import eggs' in spam/__init__.py
                       '/target/spam/eggs/__init__.py',
                       # 'import eggs' in main.py
                       '/target/eggs/__init__.py'],
                      _test_portal.files)

  def testImportModuleInsidePackage(self):
    self._env._TearDown()  # RunScript will set up the env
    self._tree.SetFile('main.py', """
_test_portal.files.append(__file__)
# spam will in turn import eggs which should be 'spam.eggs', not 'eggs'
import spam
# confirm that there is indeed a top level 'eggs'
# without this, the 'import eggs' test in spam would be incomplete
import eggs
""")
    self._tree.SetFile('spam/__init__.py', """
_test_portal.files.append(__file__)
# should import eggs from spam
import eggs
""")
    self._tree.SetFile('spam/eggs.py', """
_test_portal.files.append(__file__)
""")
    self._tree.SetFile('eggs.py', """
_test_portal.files.append(__file__)
""")
    _test_portal.files = []
    self._env.RunScript('main.py', CollectingHandler())
    self.assertEquals(['/target/main.py',
                       # 'import spam' in main.py
                       '/target/spam/__init__.py',
                       # 'import eggs' in spam/__init__.py
                       '/target/spam/eggs.py',
                       # 'import eggs' in main.py
                       '/target/eggs.py'],
                      _test_portal.files)

  def CheckPep302ModuleAttributes(self, name):
    self.assertEquals('/target/foo.py', _test_portal.__file__)
    self.assertEquals(name, _test_portal.__name__)
    self.assertIsNone(_test_portal.__path__)
    loader = _test_portal.__loader__
    self.assertTrue(isinstance(loader, target_env._Loader))
    # verify internal _Loader attributes
    self.assertTrue(isinstance(loader.env, target_env.TargetEnvironment))
    self.assertEquals('/target', loader.path)
    self.assertEquals('foo.py', loader.file_path)
    self.assertFalse(loader.is_package)

  def testPep302ModuleAttributes(self):
    self._tree.SetFile('foo.py', _PEP302_ATTRIBUTE_SCRIPT)
    import foo  # pylint: disable-msg=C6204, W0612
    self.CheckPep302ModuleAttributes('foo')

  def testPep302ModuleAttributesWithRunScript(self):
    self._env._TearDown()  # RunScript will set up the env
    self._tree.SetFile('foo.py', _PEP302_ATTRIBUTE_SCRIPT)
    self._env.RunScript('foo.py', CollectingHandler())
    self.CheckPep302ModuleAttributes('__main__')

  def CheckPep302PackageAttributes(self, name):
    self.assertEquals('/target/foo/__init__.py', _test_portal.__file__)
    self.assertEquals(name, _test_portal.__name__)
    #self.assertEquals(['/target/foo/'], _test_portal.__path__)
    self.assertEquals(['/target'], _test_portal.__path__)
    loader = _test_portal.__loader__
    self.assertTrue(isinstance(loader, target_env._Loader))
    # verify internal _Loader attributes
    self.assertTrue(isinstance(loader.env, target_env.TargetEnvironment))
    self.assertEquals('/target', loader.path)
    self.assertEquals('foo/__init__.py', loader.file_path)
    self.assertTrue(loader.is_package)

  def testPep302PackgeAttributes(self):
    self._tree.SetFile('foo/__init__.py', _PEP302_ATTRIBUTE_SCRIPT)
    import foo  # pylint: disable-msg=C6204, W0612
    self.CheckPep302PackageAttributes('foo')

  def testPep302PackageAttributesWithRunScript(self):
    self._env._TearDown()  # RunScript will set up the env
    self._tree.SetFile('foo/__init__.py', _PEP302_ATTRIBUTE_SCRIPT)
    self._env.RunScript('foo/__init__.py', CollectingHandler())
    self.CheckPep302PackageAttributes('__main__')

  def testErrorImportingPackage(self):
    # This is an odd case - if a package foo imports module bar then foo.bar
    # will exist in sys.modules even if a later exception causes foo to fail
    # import.  We need to make sure this doesn't cause a problem during cleanup.
    self._tree.SetFile('foo/__init__.py', """
import sys
raise ImportError
""")
    try:
      import foo  # pylint: disable-msg=C6204, W0612
      self.fail()
    except ImportError:
      pass
    self.assertIn('foo.sys', sys.modules)
    self.assertNotIn('foo', sys.modules)
    self._env._TearDown()
    self.assertNotIn('foo.sys', sys.modules)

  def testImportNotFound(self):
    try:
      import foo  # pylint: disable-msg=C6204, W0612
      self.fail()
    except ImportError:
      pass  # expected

  def testRunScript(self):
    self._env._TearDown()  # RunScript will set up the env
    self._tree.SetFile('d/foo.py', """
import logging
import sys
_test_portal.main = sys.modules['__main__']
logging.debug('running foo.py')
""")
    level = logging.getLogger().level
    self.assertTrue(level > logging.DEBUG)  # should be true in a test
    handler = CollectingHandler()
    self._env.RunScript('d/foo.py', handler)
    module = _test_portal.main
    self.assertEquals('__main__', module.__name__)
    self.assertEquals('/target/d/foo.py', module.__file__)
    # check that logging handler was invoked
    self.assertEquals(1, len(handler.records))
    self.assertEquals('running foo.py', handler.records[0].getMessage())
    # check logging cleanup
    self.assertEquals(level, logging.getLogger().level)

  def testMimicMainNotInSysModules(self):
    self._env._TearDown()  # RunScript will set up the env
    self._tree.SetFile('main.py', """
import logging
logging.debug('running main.py')
_test_portal.main_was_imported = True
""")
    self._tree.SetFile('d/foo.py', """
import logging
_test_portal.main_was_imported = False
# should be our main.py, not mimic's
import main
logging.debug('running foo.py')
""")
    level = logging.getLogger().level
    self.assertTrue(level > logging.DEBUG)  # should be true in a test
    handler = CollectingHandler()
    # pollute sys.modules['main'] in the same way mimic's main.py does
    sys.modules['main'] = target_env
    self._env.RunScript('d/foo.py', handler)
    self.assertTrue(_test_portal.main_was_imported)
    # check that logging handler was invoked
    self.assertEquals(2, len(handler.records))
    self.assertEquals('running main.py', handler.records[0].getMessage())
    self.assertEquals('running foo.py', handler.records[1].getMessage())
    # check logging cleanup
    self.assertEquals(level, logging.getLogger().level)

  def testRunScriptRestoresMimicModulesMaskedByUserCode(self):
    # an already loaded module which we can mask in this test
    module_key = target_env.__name__
    module_path = module_key.replace('.', '/') + '.py'
    # confirm module already loaded
    self.assertTrue(module_key in sys.modules)
    original_module = sys.modules[module_key]
    self._env._TearDown()  # RunScript will set up the env
    # attempt to mask an existing mimic module
    self._tree.SetFile(module_path, """
import sys
_test_portal.module = sys.modules['%s']
""" % module_key)
    handler = CollectingHandler()
    self._env.RunScript(module_path, handler)
    module = _test_portal.module
    self.assertEquals('__main__', module.__name__)
    self.assertEquals('/target/%s' % module_path, module.__file__)
    # check that sys.module was (temporarily) modified inside RunScript
    self.assertNotEquals(module, original_module)
    # check that sys.module has been restored
    self.assertEquals(sys.modules[module_key], original_module)

  def testRunScriptWithMainMethod(self):
    self._env._TearDown()  # RunScript will set up the env
    self._tree.SetFile('d/foo.py', """
import logging
def mainTest():
  logging.debug('running foo.py mainTest()')
""")
    level = logging.getLogger().level
    self.assertTrue(level > logging.DEBUG)  # should be true in a test
    handler = CollectingHandler()
    self._env.RunScript('d/foo.py', handler, 'mainTest()')
    # check that logging handler was invoked
    self.assertEquals(1, len(handler.records))
    self.assertEquals('running foo.py mainTest()',
                      handler.records[0].getMessage())

  def testRunScriptWithPackage(self):
    """Tests that __init__.py is run when a package is specified in script:."""
    self._env._TearDown()  # RunScript will set up the env
    self._tree.SetFile('foo/bar/__init__.py', """
import logging
logging.info('running __init__.py in foo/bar')
""")
    handler = CollectingHandler()
    self._env.RunScript('foo/bar', handler)
    # check that logging handler was invoked
    self.assertEquals(1, len(handler.records))
    self.assertEquals('running __init__.py in foo/bar',
                      handler.records[0].getMessage())

  def testSysModulesHasTwoEntriesForCurrentTopLevelScript(self):
    self._env._TearDown()  # RunScript will set up the env
    self._tree.SetFile('foo.py', """
import logging
import sys
_test_portal.main = sys.modules['__main__']
_test_portal.foo = sys.modules['foo']
logging.debug('running foo.py')
""")
    handler = CollectingHandler()
    self._env.RunScript('foo.py', handler)
    # check that logging handler was invoked
    self.assertEquals(1, len(handler.records))
    self.assertEquals('running foo.py',
                      handler.records[0].getMessage())
    module_main = _test_portal.main
    self.assertEquals('__main__', module_main.__name__)
    module_foo = _test_portal.foo
    self.assertEquals(module_foo, module_main)

  def testSysModulesHasTwoEntriesForCurrentPackageScript(self):
    self._env._TearDown()  # RunScript will set up the env
    self._tree.SetFile('d/foo.py', """
import logging
import sys
_test_portal.main = sys.modules['__main__']
_test_portal.foo = sys.modules['d.foo']
logging.debug('running foo.py')
""")
    handler = CollectingHandler()
    self._env.RunScript('d/foo.py', handler)
    # check that logging handler was invoked
    self.assertEquals(1, len(handler.records))
    self.assertEquals('running foo.py',
                      handler.records[0].getMessage())
    module_main = _test_portal.main
    self.assertEquals('__main__', module_main.__name__)
    module_foo = _test_portal.foo
    self.assertEquals(module_foo, module_main)

  def testRunScriptNotFound(self):
    self._env._TearDown()  # RunScript will set up the env
    self.assertRaises(target_env.ScriptNotFoundError,
                      self._env.RunScript, 'foo.py', CollectingHandler())

  def testOpenExternalFile(self):
    self.assertIsNotNone(self._env.OpenExternalFile(__file__))
    self.assertRaises(IOError, self._env.OpenExternalFile, '/not_a_real_file')
    self._tree.SetFile('foo.txt', 'abc')  # will be ignored
    self.assertIsNone(self._env.OpenExternalFile('foo.txt'))
    self.assertIsNone(self._env.OpenExternalFile('/target/foo.txt'))

  def testReadTargetFile(self):
    self._tree.SetFile('foo.txt', 'abc')
    self.assertEquals('abc', self._env.ReadTargetFile('foo.txt'))
    self.assertEquals('abc', self._env.ReadTargetFile('/target/foo.txt'))
    self.assertIsNone(self._env.ReadTargetFile('bar.txt'))

  def testOpenTargetFile(self):
    self._tree.SetFile('foo.txt', 'abc')
    a_file = open('foo.txt')
    self.assertTrue(isinstance(a_file, file))
    self.assertEquals('abc', a_file.read())
    self.assertRaises(IOError, open, 'bar.txt')  # file doesn't exist

  def testOpenUniversalMode(self):
    self._tree.SetFile('foo.txt', 'a\nb\rc\r\nd')
    # no conversion in normal mode
    a_file = open('foo.txt')
    self.assertEquals('a\nb\rc\r\nd', a_file.read())
    # \r and \r\n are converted to \n in universal mode
    a_file = open('foo.txt', 'U')
    self.assertEquals('a\nb\nc\nd', a_file.read())
    a_file = open('foo.txt', 'rU')
    self.assertEquals('a\nb\nc\nd', a_file.read())

  def testOpenModes(self):
    self._tree.SetFile('foo.txt', 'abc')
    # these to modes are allowed
    for mode in ['r', 'rb']:
      a_file = open('foo.txt', mode)
      self.assertTrue(isinstance(a_file, file))
    # everything else should fail
    for mode in ['r+', 'w', 'w+', 'a', 'a+']:
      self.assertRaises(IOError, open, 'foo.txt', mode)
      self.assertRaises(IOError, open, 'foo.txt', mode + 'b')

  def testOpenExternal(self):
    a_file = open(__file__)
    self.assertTrue('testOpenExternal(self)' in a_file.read())

  def testCannotWriteTargetFile(self):
    self._tree.SetFile('foo.txt', 'abc')
    a_file = open('foo.txt')
    self.assertRaises(IOError, a_file.write, 'foo')
    self.assertRaises(IOError, a_file.writelines, [])
    self.assertRaises(IOError, a_file.truncate)
    self.assertRaises(IOError, a_file.truncate, 10)

  def testFile(self):
    # open() has been thoroughly tested, so just make sure we can
    # open both target and external files via file()
    self._tree.SetFile('foo.txt', 'abc')
    a_file = file('foo.txt')
    self.assertTrue(isinstance(a_file, file))
    self.assertEquals('abc', a_file.read())
    a_file = file(__file__)
    self.assertTrue('testFile(self)' in a_file.read())

  def doGetCwdTest(self, file_path, exp_cwd, os_call='os.getcwd()',
                   exp_type=str):
    self._env._TearDown()  # RunScript will set up the env
    self._tree.SetFile(file_path, """
import os
import logging
logging.debug(%s)
""" % os_call)
    handler = CollectingHandler()
    self._env.RunScript(file_path, handler)
    msg = handler.records[0].getMessage()
    self.assertEquals(exp_cwd, msg)
    self.assertTrue(isinstance(msg, exp_type))

  def testGetCwdAtRoot(self):
    self.doGetCwdTest('foo.py', '/target')

  def testGetCwdInFolder(self):
    self.doGetCwdTest('dir/foo.py', '/target/dir')

  def testGetCwdu(self):
    self.doGetCwdTest('foo.py', '/target', 'os.getcwdu()', unicode)

  def testAccess(self):
    self._tree.SetFile('foo.txt', 'abc')
    self._tree.SetFile('d/bar.txt', 'def')
    self._tree.SetFile('static/index.html', 'static html')
    self._tree.SetFile('stylesheets/index.css', 'static css')
    self.assertTrue(os.access('foo.txt', os.F_OK))
    self.assertTrue(os.access('foo.txt', os.R_OK))
    self.assertFalse(os.access('foo.txt', os.W_OK))
    self.assertFalse(os.access('foo.txt', os.X_OK))
    self.assertFalse(os.access('foo.txt', os.R_OK | os.W_OK))
    self.assertTrue(os.access('/target/foo.txt', os.F_OK))
    self.assertFalse(os.access('bar.txt', os.F_OK))
    self.assertFalse(os.access('/target/bar.txt', os.F_OK))
    # directories
    self.assertTrue(os.access('/target', os.F_OK))
    self.assertTrue(os.access('/target/d', os.F_OK))
    self.assertTrue(os.access('d', os.F_OK))
    self.assertFalse(os.access('/target/f', os.F_OK))
    self.assertTrue(os.access('d', os.R_OK))
    self.assertTrue(os.access('d', os.X_OK))
    self.assertFalse(os.access('d', os.R_OK | os.W_OK))
    self.assertFalse(os.access('d', os.W_OK))
    # check external files
    self.assertTrue(os.access(__file__, os.F_OK))
    self.assertFalse(os.access('not_a_file', os.F_OK))
    # check static files
    # In production, whether or not a folder in a static_files handler is
    # accessible to a script file depends on if all the files in the folder are
    # matched by the handler, in which case the folder isn't uploaded, and thus
    # isn't accessible to script. We don't check for this, so the folder in
    # a static_files handler is always available to script. So, for example,
    # this won't pass: self.assertFalse(os.access('static', os.F_OK))
    self.assertFalse(os.access('static/index.html', os.F_OK))
    self.assertFalse(os.access('stylesheets/index.css', os.F_OK))
    self.assertFalse(os.access('stylesheets', os.F_OK))
    self.assertFalse(os.access('stylesheets_other', os.F_OK))
    # check skipped files
    self.assertFalse(os.access('README.txt', os.F_OK))
    self.assertFalse(os.access('/target/README.txt', os.F_OK))
    self.assertFalse(os.access('skip_folder', os.F_OK))
    self.assertFalse(os.access('/target/skip_folder', os.F_OK))
    self.assertFalse(os.access('/target/skip_folder/file', os.F_OK))

  def testListDir(self):
    self._tree.SetFile('foo', '')
    self._tree.SetFile('d/bar', '')
    self._tree.SetFile('d/baz', '')
    self.assertItemsEqual(['foo', 'd'], os.listdir('.'))
    self.assertItemsEqual(['foo', 'd'], os.listdir('/target'))
    self.assertItemsEqual(['bar', 'baz'], os.listdir('d'))
    self.assertItemsEqual(['bar', 'baz'], os.listdir('/target/d'))
    self.assertRaises(OSError, os.listdir, 'foo')  # foo is a file
    self.assertRaises(OSError, os.listdir, 'does-not-exist')
    # check that unicode strings are returned if path is unicode
    self.assertFalse(isinstance(os.listdir('.')[0], unicode))
    self.assertTrue(isinstance(os.listdir(u'.')[0], unicode))
    # check external dir still works
    parent, basename = os.path.split(__file__)
    self.assertIn(basename, os.listdir(parent))
    # check that /target appears in /
    self.assertIn('target', os.listdir('/'))

  def testIsDirFile(self):
    """Test os.path.isdir and os.path.isfile."""

    def CheckDir(path):
      self.assertTrue(os.path.isdir(path))
      self.assertFalse(os.path.isfile(path))

    def CheckFile(path):
      self.assertFalse(os.path.isdir(path))
      self.assertTrue(os.path.isfile(path))

    self._tree.SetFile('foo', '')
    self._tree.SetFile('d/bar', '')
    self._tree.SetFile('d/baz', '')

    # target
    CheckDir('/target')
    CheckDir('.')
    CheckDir('d')
    CheckFile('foo')
    CheckFile('d/bar')
    self.assertFalse(os.path.isdir('does-not-exist'))
    self.assertFalse(os.path.isfile('does-not-exist'))
    # external
    CheckDir(os.path.dirname(__file__))
    CheckFile(__file__)

  def testSymLinks(self):
    """Tests for os.path.islink."""
    # Since symlinks don't exist in /target, the only real difference between
    # patched and unpatched versions is how they treat relative paths.  So
    # this test creates a symlink in a temp directory and changes to that
    # directory outside of a TargetEnv.  The test then verifies that relative
    # paths resolve to within /target and external symlinks still work.
    self._tree.SetFile('abc', '')
    self._env._TearDown()  # need to chdir in unpatched os
    tmp = tempfile.mkdtemp()
    original_wd = os.getcwd()
    os.chdir(tmp)
    try:
      open('foo', 'w').close()  # create file foo
      os.symlink('foo', 'bar')  # create symlink bar
      # just a sanity check that we set up the right thing
      self.assertTrue(os.path.islink('bar'))
      # restablish TargetEnv
      self._env._SetUp()
      self.assertFalse(os.path.islink('bar'))  # /target/bar does not exist
      self.assertFalse(os.path.islink('abc'))  # /target/abc is a file
      # external paths still ok
      self.assertFalse(os.path.islink(os.path.join(tmp, 'foo')))
      self.assertTrue(os.path.islink(os.path.join(tmp, 'bar')))
    finally:
      os.chdir(original_wd)
      shutil.rmtree(tmp)

  def testWalk(self):
    # os.walk() should work since it is built on top of os.listdir() and
    # os.path.isdir().  Run a few simple tests just to check.
    self._tree.SetFile('foo', '')
    self._tree.SetFile('d/bar', '')
    self._tree.SetFile('d/baz', '')
    # walk /target
    results = list(os.walk('.'))
    self.assertEquals(('.', ['d'], ['foo']), results[0])
    results[1][2].sort()  # sort to make test deterministic
    self.assertEquals(('./d', [], ['bar', 'baz']), results[1])
    # walking / should have target in its list of directories
    for _, dirs, _ in os.walk('/'):
      self.assertIn('target', dirs)
      del dirs[:]  # this will end the walk

  def CheckUnlink(self, func):
    # not allowed to modify target files
    self._tree.SetFile('foo', 'abc')
    self.assertRaises(OSError, func, 'foo.txt')
    # can unlink external files
    tmp = tempfile.mkdtemp()
    try:
      path = os.path.join(tmp, 'foo')
      open(path, 'w').close()  # create file
      func(path)
      self.assertFalse(os.access(path, os.F_OK))
    finally:
      shutil.rmtree(tmp)

  def testRemove(self):
    self.CheckUnlink(os.remove)

  def testUnlink(self):
    self.CheckUnlink(os.unlink)

  def testRename(self):
    # not allowed to modify target files
    self._tree.SetFile('t1', 'abc')
    self.assertRaises(OSError, os.rename, 't1', 't2')
    # try external files
    tmp = tempfile.mkdtemp()
    try:
      src = os.path.join(tmp, 'foo')
      dst = os.path.join(tmp, 'bar')
      open(src, 'w').close()  # create file
      # can't rename between target and external
      self.assertRaises(OSError, os.rename, src, 't2')
      self.assertRaises(OSError, os.rename, 't1', dst)
      # can rename external file to another external path
      os.rename(src, dst)
      self.assertFalse(os.access(src, os.F_OK))
      self.assertTrue(os.access(dst, os.F_OK))
    finally:
      shutil.rmtree(tmp)

  def testBlobstoreGetBlobKey(self):
    # Create the file
    file_name = files.blobstore.create(mime_type='application/octet-stream')
    # Open the file and write to it
    with files.open(file_name, 'a') as f:
      f.write('data')
    # Finalize the file. Do this before attempting to read it.
    files.finalize(file_name)
    # Get the file's blob key, calls datastore.Key.from_path
    self.blob_key = files.blobstore.get_blob_key(file_name)
    # the fact that we're able to get a key means our Key.from patch is working
    self.assertIsNotNone(self.blob_key)
    self.assertTrue(isinstance(self.blob_key, blobstore.BlobKey))
    self.blob_key_str = str(self.blob_key)
    # for sanity, verify non-zero length string blob key
    self.assertTrue(len(self.blob_key_str))

  def testIsStaticFile(self):
    # see _TEST_CONFIG
    self.assertFalse(self._env._IsStaticFile('main.py'))
    self.assertFalse(self._env._IsStaticFile('/target/main.py'))

    # test static_dir
    self.assertTrue(self._env._IsStaticFile('stylesheets/main.css'))
    self.assertTrue(self._env._IsStaticFile('/target/stylesheets/main.css'))
    self.assertTrue(self._env._IsStaticFile('stylesheets/'))
    self.assertTrue(self._env._IsStaticFile('/target/stylesheets/'))
    self.assertTrue(self._env._IsStaticFile('stylesheets'))
    self.assertTrue(self._env._IsStaticFile('/target/stylesheets'))
    self.assertFalse(self._env._IsStaticFile('stylesheets_other'))
    self.assertFalse(self._env._IsStaticFile('/target/stylesheets_other'))
    self.assertFalse(self._env._IsStaticFile('stylesheetsabc'))
    self.assertFalse(self._env._IsStaticFile('/target/stylesheetsabc'))

    # test static_files
    self.assertTrue(self._env._IsStaticFile('static/pic.jpg'))
    self.assertTrue(self._env._IsStaticFile('/target/static/pic.jpg'))

    self.assertTrue(self._env._IsStaticFile('static/index.html'))
    self.assertTrue(self._env._IsStaticFile('/target/static/index.html'))

  def testStaticFilesBadRegex(self):
    self._env._TearDown()
    config = yaml.load(r"""
handlers:
- url: /.*
  static_files: static/\1
  # invalid regex
  upload: static/**
""")
    self.assertRaises(
        target_info.ValidationError,
        target_env.TargetEnvironment,
        self._tree,
        config,
        'ProjectName',
        test_portal=_test_portal)

  def testOpenStaticFile(self):
    self._env._TearDown()  # RunScript will set up the env
    self._tree.SetFile('template.html', 'template text')
    self._tree.SetFile('static/index.html', 'index text')
    self._tree.SetFile('main.py', """
import logging
import os

# this should be fine
f = open('template.html')
logging.info(f.read())

try:
  open('static/index.html')
except IOError, e:
  logging.error('got IOError: ' + str(e.errno))

# results in "/target/static/index.html"
path = os.path.join(os.path.dirname(__file__), 'static/index.html')
try:
  open(path)
except IOError, e:
  logging.error('got IOError: ' + str(e.errno))

try:
  # should match static_dir
  open('stylesheets/main.css')
except IOError, e:
  logging.error('got IOError: ' + str(e.errno))

try:
  # doesn't exist
  open('/static/index.html')
except IOError, e:
  logging.error('got IOError: ' + str(e.errno))
""")
    handler = CollectingHandler()
    self._env.RunScript('main.py', handler)
    self.assertEqual('template text', handler.records[0].getMessage())
    no_ent_error_msg = 'got IOError: ' + str(errno.ENOENT)
    self.assertEqual(no_ent_error_msg, handler.records[1].getMessage())
    self.assertEqual(no_ent_error_msg, handler.records[2].getMessage())
    self.assertEqual(no_ent_error_msg, handler.records[3].getMessage())
    self.assertEqual(no_ent_error_msg, handler.records[4].getMessage())

  def testStatOnFile(self):
    """Tests patched stat on a file in the target file system."""
    self._env._TearDown()  # RunScript will set up the env
    self._tree.SetFile('template.html', 'template text')
    self._tree.SetFile('main.py', """
import os
import logging
import stat

stats = os.stat('template.html')
logging.info(stats[stat.ST_MODE])
# also test accessing the stat values as attributes
logging.info(stats.st_size)
""")
    handler = CollectingHandler()
    self._env.RunScript('main.py', handler)
    self.assertEqual(str(target_env._FILE_STAT_MODE),
                     handler.records[0].getMessage())
    self.assertEqual('13', handler.records[1].getMessage())

  def testStatOnDirectory(self):
    """Tests patched stat on a directory in the target file system."""
    self._env._TearDown()  # RunScript will set up the env
    self._tree.SetFile('templates/template.html', 'template text')
    self._tree.SetFile('main.py', """
import os
import logging
import stat

stats = os.stat('templates')
logging.info(stats[stat.ST_MODE])
# also test accessing the stat values as attributes
logging.info(stats.st_size)
""")
    handler = CollectingHandler()
    self._env.RunScript('main.py', handler)
    self.assertEqual(str(target_env._DIR_STAT_MODE),
                     handler.records[0].getMessage())
    self.assertEqual('0', handler.records[1].getMessage())

  def testStatOnStaticFile(self):
    """Tests that patched stat raises an OSError on a static file."""
    self._env._TearDown()  # RunScript will set up the env
    self._tree.SetFile('static/index.html', 'index text')
    self._tree.SetFile('main.py', """
import os
import logging

for path in ('static/index.html', 'stylesheets/main.css'):
  try:
    # this is in the target file system, but matched by a static handler
    os.stat(path)
  except OSError, e:
    logging.info('got OSError')

  path = os.path.join(os.path.dirname(__file__), path)
  try:
    # this is in the target file system, but matched by a static handler, and
    # should be prefixed by "/target"
    os.stat(path)
  except OSError, e:
    logging.info('got OSError')
""")
    handler = CollectingHandler()
    self._env.RunScript('main.py', handler)
    # two for 'static/index.html', and two for 'stylesheets/main.css'
    self.assertEqual('got OSError', handler.records[0].getMessage())
    self.assertEqual('got OSError', handler.records[1].getMessage())
    self.assertEqual('got OSError', handler.records[2].getMessage())
    self.assertEqual('got OSError', handler.records[3].getMessage())

  def testStatFileDoesNotExist(self):
    """Tests that patched stat raises OSError on a file that doesn't exist."""
    self._env._TearDown()  # RunScript will set up the env
    self._tree.SetFile('main.py', """
import os
import logging

try:
  # this is in the target file system
  os.stat('template.html')
except OSError, e:
  logging.info('got OSError: ' + str(e.errno))

try:
  # this should go through the original stat
  os.stat('/folder-foo/file-baz')
except OSError, e:
  logging.info('got OSError: ' + str(e.errno))
""")
    handler = CollectingHandler()
    self._env.RunScript('main.py', handler)
    no_ent_error_msg = 'got OSError: ' + str(errno.ENOENT)
    self.assertEqual(no_ent_error_msg, handler.records[0].getMessage())
    self.assertEqual(no_ent_error_msg, handler.records[1].getMessage())

  def testCreateSkipFilesPattern(self):
    # test that _skip_files_pattern was created when the target environment
    # was set up in setUp()
    self.assertIsNotNone(self._env._skip_files_pattern)
    self.assertIsNone(self._env._CreateSkipFilesPattern(None))
    self.assertIsNone(self._env._CreateSkipFilesPattern({}))
    regex = self._env._CreateSkipFilesPattern({'skip_files': ['^file$', 'abc']})
    self.assertEqual(re.compile('(?:^file$)|(?:abc)'), regex)
    self.assertIsNotNone(regex.match('file'))
    self.assertIsNotNone(regex.match('abc'))
    self.assertIsNotNone(regex.match('abcfile'))
    self.assertIsNone(regex.match('pic.jpg'))

  def testIsSkippedFile(self):
    # see _TEST_CONFIG
    self.assertTrue(self._env._IsSkippedFile('README.txt'))
    self.assertTrue(self._env._IsSkippedFile('/target/folder/README.txt'))
    self.assertTrue(self._env._IsSkippedFile('skip_folder/some_test.py'))
    self.assertTrue(self._env._IsSkippedFile('/target/skip_folder/file.py'))
    self.assertTrue(self._env._IsSkippedFile('skip_folder/folder/some_test.py'))
    # not skipped files
    self.assertFalse(self._env._IsSkippedFile('main.py'))
    self.assertFalse(self._env._IsSkippedFile('/target/main.py'))
    self.assertFalse(self._env._IsSkippedFile('pic.jpg'))
    self.assertFalse(self._env._IsSkippedFile('/target/pic.jpg'))

  def testOpenSkippedFile(self):
    self._env._TearDown()  # RunScript will set up the env
    self._tree.SetFile('README.txt', 'readme')
    self._tree.SetFile('folder/README.txt', 'readme too')
    self._tree.SetFile('skip_folder/skipped.txt', 'skip me')
    self._tree.SetFile('main.py', """
import logging
for file in ('README.txt', 'folder/README.txt', 'skip_folder/skipped.txt'):
  for file2 in (file, '/target/' + file):
    try:
      open(file2)
    except IOError, e:
      logging.error('got IOError: ' + str(e.errno))
""")
    handler = CollectingHandler()
    self._env.RunScript('main.py', handler)
    no_ent_error_msg = 'got IOError: ' + str(errno.ENOENT)
    self.assertEqual(6, len(handler.records))
    for record in handler.records:
      self.assertEqual(no_ent_error_msg, record.getMessage())

  def testStatOnSkippedFile(self):
    """Tests patched stat on a skipped file."""
    self._env._TearDown()  # RunScript will set up the env
    self._tree.SetFile('README.txt', 'readme')
    self._tree.SetFile('folder/README.txt', 'readme too')
    self._tree.SetFile('skip_folder/file', 'skipme')
    self._tree.SetFile('main.py', """
import logging
import os
for file in ('README.txt', 'folder/README.txt', 'skip_folder/skipped.txt'):
  for file2 in (file, '/target/' + file):
    try:
      os.stat(file2)
    except OSError, e:
      logging.error('got OSError: ' + str(e.errno))
""")
    handler = CollectingHandler()
    self._env.RunScript('main.py', handler)
    no_ent_error_msg = 'got OSError: ' + str(errno.ENOENT)
    self.assertEqual(6, len(handler.records))
    for record in handler.records:
      self.assertEqual(no_ent_error_msg, record.getMessage())

  def testSkipFilesBadRegex(self):
    self._env._TearDown()
    config = yaml.load(r"""
handlers:
- url: /.*
  script: main.py

skip_files:
# invalid
- '*'
""")
    try:
      target_env.TargetEnvironment(self._tree, config, 'ProjectName',
                                   test_portal=_test_portal)
      # the constructor should raise an exception
      self.fail()
    except target_info.ValidationError, e:
      # make sure it's the right valididation error
      self.assertTrue('skip_files' in str(e))


class AddPatchTest(unittest.TestCase):
  def setUp(self):
    self.count = 0

  def Install(self):
    self.count += 1

  def Remove(self):
    self.count -= 1

  def testAddPatch(self):
    env = target_env.TargetEnvironment(
        None,
        _TEST_CONFIG,
        'ProjectName')
    env.AddPatch(self)
    self.assertEquals(0, self.count)
    env._SetUp()
    self.assertEquals(1, self.count)
    env._TearDown()
    self.assertEquals(0, self.count)


class TestResolvePath(unittest.TestCase):
  def Check(self, in_target, expected_path, path):
    self.assertEquals((in_target, expected_path), target_env._ResolvePath(path))

  def testTarget(self):
    self.Check(True, 'a/b', '/target/a/b')
    self.Check(True, 'a/b', 'a/b')
    self.Check(True, 'a/b', 'a/b/')
    self.Check(True, '', '/target')
    self.Check(True, '', '/target/')
    self.Check(True, '', '.')
    self.Check(True, 'b/c', '/target/a/../b/c')
    self.Check(True, 'b/c', 'a/../b/c')

  def testExternal(self):
    self.Check(False, '/a/b', '/a/b')
    self.Check(False, '/a/b', '/a/b/')
    self.Check(False, '/b', '/a/../b')
    self.Check(False, '/a/b', '../a/b')
    self.Check(False, '/', '/')
    self.Check(False, '/', '/..')
    self.Check(False, '/', '/../..')
    self.Check(False, '/targetx', '/targetx')
    self.Check(False, '/targetx', '/targetx/')


if __name__ == '__main__':
  unittest.main()
