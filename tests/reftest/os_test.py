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

"""Tests related to the os module."""



import os
import unittest


class OsTest(unittest.TestCase):
  """Very simple tests to verify that os is patched."""

  def testOsFunctions(self):
    self.assertTrue(os.access(__file__, os.F_OK))
    self.assertEquals('/target', os.getcwd())
    self.assertEquals('/target', os.getcwdu())
    self.assertTrue('foo.txt' in os.listdir('/target'))
    self.assertRaises(OSError, os.remove, __file__)
    self.assertRaises(OSError, os.unlink, __file__)
    self.assertRaises(OSError, os.rename, __file__, 'foo')
    self.assertTrue(os.path.isdir('/target'))
    self.assertTrue(os.path.isfile(__file__))
    self.assertFalse(os.path.islink(__file__))
