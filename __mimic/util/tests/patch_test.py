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

"""Unit tests for patch.py."""



import __builtin__
import sys

from __mimic.util import patch

import unittest


class BuiltinPatchTest(unittest.TestCase):
  """Unit tests for Patch."""

  def setUp(self):
    self._patch = None

  def tearDown(self):
    if self._patch:
      self._patch.Remove()

  def testPatch(self):
    self._patch = patch.BuiltinPatch('abs', lambda x: x)
    self.assertEquals(3, abs(-3))
    self._patch.Install()
    self.assertEquals(-3, abs(-3))
    self.assertTrue(self._patch.installed)
    self._patch.Remove()
    self.assertEquals(3, abs(-3))
    self.assertFalse(self._patch.installed)

  def testNeedsOriginal(self):

    @patch.NeedsOriginal
    def DoubleAbs(original, x):
      return original(x) * 2

    self._patch = patch.BuiltinPatch('abs', DoubleAbs)
    self.assertEquals(7, abs(-7))
    self._patch.Install()
    self.assertEquals(14, abs(-7))
    self._patch.Remove()
    self.assertEquals(7, abs(-7))

  def testCustomBuiltins(self):
    def CustomAbs(x):
      return x * x

    def PatchedAbs(x):
      return x

    self._patch = patch.BuiltinPatch('abs', PatchedAbs)
    original_abs = __builtin__.abs
    saved_builtins = patch.__builtins__
    custom_builtins = patch._GetBuiltinsDict().copy()
    custom_builtins['abs'] = CustomAbs
    try:
      patch.__builtins__ = custom_builtins
      self._patch.Install()
      self.assertEquals(PatchedAbs, __builtin__.abs)
      self.assertEquals(PatchedAbs, patch.__builtins__['abs'])
      self.assertEquals(CustomAbs, self._patch._original)
      self._patch.Remove()
      self.assertEquals(original_abs, __builtin__.abs)
      self.assertEquals(CustomAbs, patch.__builtins__['abs'])
    finally:
      patch.__builtins__ = saved_builtins


def Square(x):
  return x * x


class AttributePatchTest(unittest.TestCase):
  def testPatch(self):
    module = sys.modules[__name__]
    a_patch = patch.AttributePatch(module, 'Square', lambda x: x)
    self.assertEquals(25, Square(5))
    a_patch.Install()
    self.assertEquals(5, Square(5))
    self.assertTrue(a_patch.installed)
    a_patch.Remove()
    self.assertEquals(25, Square(5))
    self.assertFalse(a_patch.installed)

  def testNeedsOriginal(self):

    @patch.NeedsOriginal
    def NegativeSquare(original, x):
      return -original(x)

    module = sys.modules[__name__]
    a_patch = patch.AttributePatch(module, 'Square', NegativeSquare)
    self.assertEquals(25, Square(5))
    a_patch.Install()
    self.assertEquals(-25, Square(5))
    a_patch.Remove()
    self.assertEquals(25, Square(5))


class Math(object):

  @staticmethod
  def Tripple(x):
    return 3 * x


class AttributePatchStaticTest(unittest.TestCase):
  def testPatch(self):
    a_patch = patch.AttributePatch(Math, 'Tripple', lambda x: x)
    self.assertEquals(15, Math.Tripple(5))
    a_patch.Install()
    self.assertEquals(5, Math.Tripple(5))
    self.assertTrue(a_patch.installed)
    a_patch.Remove()
    self.assertEquals(15, Math.Tripple(5))
    self.assertFalse(a_patch.installed)

  def testNeedsOriginal(self):

    @patch.NeedsOriginal
    def NegativeTripple(original, x):
      return -original(x)

    a_patch = patch.AttributePatch(Math, 'Tripple', NegativeTripple)
    self.assertEquals(15, Math.Tripple(5))
    a_patch.Install()
    self.assertEquals(-15, Math.Tripple(5))
    a_patch.Remove()
    self.assertEquals(15, Math.Tripple(5))


if __name__ == '__main__':
  unittest.main()
