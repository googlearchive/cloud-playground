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

"""Unit tests for common.py."""



from __mimic import common
from tests import test_util

from google.appengine.api import memcache

import unittest


class PersistTest(unittest.TestCase):
  """Unit tests for persisted values."""

  def setUp(self):
    test_util.InitAppHostingApi()

  def testNoValue(self):
    self.assertIsNone(common.GetPersistent('foo'))

  def testSet(self):
    common.SetPersistent('foo', '123')
    common.SetPersistent('bar', '456')
    self.assertEquals('123', common.GetPersistent('foo'))
    self.assertEquals('456', common.GetPersistent('bar'))
    common.SetPersistent('foo', '999')
    self.assertEquals('999', common.GetPersistent('foo'))

  def testDatastore(self):
    common.SetPersistent('foo', '123')
    memcache.flush_all()  # wipe out memcache
    self.assertEquals('123', common.GetPersistent('foo'))

  def testClear(self):
    common.SetPersistent('foo', '123')
    common.ClearPersistent('foo')
    self.assertIsNone(common.GetPersistent('foo'))
    common.ClearPersistent('foo')  # should be idempotent

  @common.RequiresOriginalMemcache
  def RequiresOriginalMemcacheTestMethod(self, arg1, arg2=0):
    self.assertTrue(common.ShouldUseOriginalMemcache())
    ret_val = self.RequiresOriginalMemcacheTestMethod2(arg1, arg2)
    # should still be using original memcache methods
    self.assertTrue(common.ShouldUseOriginalMemcache())
    return ret_val

  @common.RequiresOriginalMemcache
  def RequiresOriginalMemcacheTestMethod2(self, arg1, arg2):
    """Another method with RequiresOriginalMemcache to test reentrancy."""
    self.assertTrue(common.ShouldUseOriginalMemcache())
    self.assertEquals(1, arg1)
    self.assertEquals(3, arg2)
    return arg1 + arg2

  def testRequiresOriginalMemcacheDecorator(self):
    self.assertFalse(common.ShouldUseOriginalMemcache())
    ret = self.RequiresOriginalMemcacheTestMethod(1, arg2=3)
    self.assertEquals(ret, 4)
    self.assertFalse(common.ShouldUseOriginalMemcache())


if __name__ == '__main__':
  unittest.main()
