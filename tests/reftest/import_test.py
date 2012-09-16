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

"""Tests related to importing modules.

Some of this is a little redundant because simply importing and executing
this module exercises the basic import machinery.
"""



import sys
import unittest


class ImportTest(unittest.TestCase):
  def testMainModule(self):
    # check that main shows up in sys.modules
    module = sys.modules['__main__']
    self.assertEquals('__main__', module.__name__)
    self.assertTrue(module.__file__.endswith('main.py'))
    self.assertTrue(hasattr(module, 'CreateTestSuite'))

  def testSimpleImport(self):
    # check that this module was imported correctly
    self.assertTrue(__file__.endswith('import_test.py'))
    self.assertEquals('import_test', __name__)
    module = sys.modules['import_test']
    self.assertEquals(module.ImportTest, ImportTest)

  def testSubModule(self):
    # if this import succeeds then things are probably good
    import a_package.a_module  # pylint: disable-msg=C6204
    # spot-check a few things about the package and module
    self.assertEquals('a_package', a_package.__name__)
    self.assertEquals(123, a_package.X)
    self.assertEquals('a_package.a_module', a_package.a_module.__name__)
    self.assertEquals(456, a_package.a_module.Y)
