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

"""Unit tests for lazy.py."""



from __mimic.util import lazy

import unittest


class WithoutBase(object):
  """An object with two lazy properties."""

  def __init__(self, x):
    self.x = x
    self.calls = 0

  @lazy.LazyProperty
  def square(self):  # pylint: disable-msg=C6409
    """The square of x."""
    self.calls += 1
    return self.x * self.x

  @lazy.LazyProperty
  def cube(self):  # pylint: disable-msg=C6409
    """The cube of x."""
    self.calls += 1
    return self.x * self.x * self.x


class LazyPropertyTest(unittest.TestCase):
  """Tests for LazyProperty."""

  def testWithoutBase(self):
    obj = WithoutBase(3)
    self.assertEquals(9, obj.square)
    obj.x = 4
    # will return cached value for square
    self.assertEquals(9, obj.square)
    self.assertEquals(1, obj.calls)
    # will compute new value for cube
    self.assertEquals(64, obj.cube)
    self.assertEquals(2, obj.calls)
    # will continue to cache both values
    self.assertEquals(9, obj.square)
    self.assertEquals(64, obj.cube)
    self.assertEquals(2, obj.calls)


class WithBase(lazy.LazyBase):
  """A subclass of LazyBase with a LazyProperty."""

  def __init__(self, x):
    lazy.LazyBase.__init__(self)
    self.x = x
    self.calls = 0

  @lazy.LazyProperty
  def square(self):  # pylint: disable-msg=C6409
    """The square of x."""
    self.calls += 1
    return self.x * self.x


class LazyBaseTest(unittest.TestCase):
  """Tests for LazyBase."""

  def testWithBase(self):
    obj = WithBase(3)
    self.assertEquals(9, obj.square)
    obj.x = 4
    self.assertEquals(9, obj.square)
    self.assertEquals(1, obj.calls)
    # force property to be recomputed
    obj.ClearLazyValues()
    self.assertEquals(16, obj.square)
    self.assertEquals(2, obj.calls)


if __name__ == '__main__':
  unittest.main()
