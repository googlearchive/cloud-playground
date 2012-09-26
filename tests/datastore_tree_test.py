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

"""Unit tests for datastore_tree."""



from __mimic import datastore_tree
from tests import test_util

import unittest


class DatastoreTreeTest(unittest.TestCase):
  """Unit tests for DatastoreTree."""

  def setUp(self):
    test_util.InitAppHostingApi()
    self._tree = datastore_tree.DatastoreTree()
    self._tree.Clear()
    self._tree.SetFile('/foo', '123')
    self._tree.SetFile('/bar', '456')

  def testIsMutable(self):
    self.assertTrue(self._tree.IsMutable())

  def testGetFileContents(self):
    self.assertEquals('123', self._tree.GetFileContents('/foo'))
    self.assertEquals('456', self._tree.GetFileContents('/bar'))
    self.assertIsNone(self._tree.GetFileContents('/foobar'))

  def testHasFile(self):
    self.assertTrue(self._tree.HasFile('/foo'))
    self.assertTrue(self._tree.HasFile('/bar'))
    self.assertFalse(self._tree.HasFile('/foobar'))

  def testGetFileSize(self):
    self.assertEquals(3, self._tree.GetFileSize('/foo'))
    self.assertIsNone(self._tree.GetFileSize('/fooz'))

  def testMoveFile(self):
    self.assertTrue(self._tree.HasFile('/foo'))
    self.assertFalse(self._tree.HasFile('/foo/fooz'))
    self.assertIsNone(self._tree.GetFileContents('/foo/fooz'))
    self.assertEquals('123', self._tree.GetFileContents('/foo'))
    self._tree.MoveFile('/foo', '/foo/fooz')
    self.assertFalse(self._tree.HasFile('/foo'))
    self.assertTrue(self._tree.HasFile('/foo/fooz'))
    self.assertIsNone(self._tree.GetFileContents('/foo'))
    self.assertEquals('123', self._tree.GetFileContents('/foo/fooz'))

  def testDeleteFile(self):
    self.assertTrue(self._tree.HasFile('/foo'))
    self.assertEquals('123', self._tree.GetFileContents('/foo'))
    self._tree.DeletePath('/foo')
    self.assertFalse(self._tree.HasFile('/foo'))
    self.assertIsNone(self._tree.GetFileContents('/foo'))
    # make sure '/bar' still exists
    self.assertEquals('456', self._tree.GetFileContents('/bar'))

  def testDeleteDirectory(self):
    self.assertTrue(self._tree.HasDirectory('/'))
    self.assertFalse(self._tree.HasDirectory('/boo'))
    self.assertTrue(self._tree.HasFile('/foo'))
    self.assertEquals('123', self._tree.GetFileContents('/foo'))
    # create directory /boo with two files
    self._tree.SetFile('/boo/bat', '456')
    self._tree.SetFile('/boo/bot', '789')
    self.assertTrue(self._tree.HasDirectory('/boo'))
    self.assertTrue(self._tree.HasFile('/boo/bat'))
    self.assertEquals('456', self._tree.GetFileContents('/boo/bat'))
    self.assertTrue(self._tree.HasFile('/boo/bot'))
    self.assertEquals('789', self._tree.GetFileContents('/boo/bot'))
    # delete directory
    self._tree.DeletePath('/boo')
    self.assertTrue(self._tree.HasDirectory('/'))
    self.assertFalse(self._tree.HasDirectory('/boo'))
    self.assertTrue(self._tree.HasFile('/foo'))
    self.assertEquals('123', self._tree.GetFileContents('/foo'))
    self.assertFalse(self._tree.HasFile('/boo/bat'))
    self.assertIsNone(self._tree.GetFileContents('/boo/bat'))
    self.assertFalse(self._tree.HasFile('/boo/bot'))
    self.assertIsNone(self._tree.GetFileContents('/boo/bot'))

  def testHasDirectory(self):
    self.assertTrue(self._tree.HasDirectory('/'))
    self.assertFalse(self._tree.HasDirectory('/boo'))
    self._tree.SetFile('/boo/bat', '456')
    self.assertTrue(self._tree.HasDirectory('/boo'))
    self._tree.Clear()
    self.assertTrue(self._tree.HasDirectory('/'))

  def ListDirectory(self):
    self.assertEquals(set(('/foo', '/bar')), set(self._tree.ListDirectory('/')))
    self._tree.Clear()
    self.assertEquals(set(), set(self._tree.ListDirectory('/')))

  def testClear(self):
    self._tree.Clear()
    self.assertFalse(self._tree.HasFile('/foo'))
    self.assertFalse(self._tree.HasFile('/bar'))
    self.assertFalse(self._tree.HasFile('/foobar'))
    # check that changes persist to a new instance
    tree = datastore_tree.DatastoreTree()
    self.assertFalse(tree.HasFile('/foo'))
    self.assertFalse(tree.HasFile('/bar'))
    self.assertFalse(tree.HasFile('/foobar'))

  def testSetFile(self):
    self._tree.SetFile('/foo', 'xyz')
    self.assertEquals('xyz', self._tree.GetFileContents('/foo'))
    # check that changes persist to a new instance
    tree = datastore_tree.DatastoreTree()
    self.assertEquals('xyz', tree.GetFileContents('/foo'))


if __name__ == '__main__':
  unittest.main()
