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

"""Unit tests for composite_query.py."""



from __mimic import common
from __mimic import composite_query
from tests import test_util

from google.appengine.api import datastore_errors
from google.appengine.ext import db

import unittest

# A query limit large enough to return all data.
_BIG_ENOUGH = 100

_MODULE_SETUP = False


class Item(db.Model):
  """A simple entity with 3 integer properties."""
  x = db.IntegerProperty()
  y = db.IntegerProperty()
  z = db.IntegerProperty()

# Having a root entity key allows us to use ancestor queries for strong
# consistency in the High Replication Datastore. We initialize this global
# variable in setUp after calling test_util.InitAppHostingApi().
_ROOT_ITEM_KEY = None


class CompositeQueryTest(unittest.TestCase):
  def setUp(self):
    setUp()
    self._patch = composite_query.CompositeQueryPatch()
    self._patch.Install()

  def tearDown(self):
    self._patch.Remove()

  def CheckQuery(self, expected, query):
    query.ancestor(_ROOT_ITEM_KEY)
    # first check fetching all
    self.assertListEqual(
        expected, [e.key().name() for e in query.fetch(_BIG_ENOUGH)])
    # try a slice
    self.assertListEqual(
        expected[1:3], [e.key().name() for e in query.fetch(limit=2, offset=1)])

  def testSimpleQuery(self):
    # shouldn't require composite index
    query = db.Query(Item)
    query.filter('x =', 1)
    query.filter('y =', 2)
    self.CheckQuery(['120', '121', '122', '123', '124'], query)

  def testDescendingOrder(self):
    query = db.Query(Item)
    query.filter('x =', 1)
    query.filter('y =', 2)
    query.order('-z')
    self.CheckQuery(['124', '123', '122', '121', '120'], query)

  def testNonEqFilter(self):
    query = db.Query(Item)
    query.filter('x =', 1)
    query.filter('y >', 3)
    self.CheckQuery(['140', '141', '142', '143', '144'], query)

  def testEmptyResult(self):
    query = db.Query(Item)
    query.filter('x =', 1)
    query.filter('y >', 10)
    self.CheckQuery([], query)

  def testKeysOnly(self):
    query = db.Query(Item, keys_only=True)
    query.filter('x =', 1)
    query.filter('y >', 3)
    self.assertListEqual(['140', '141', '142', '143', '144'],
                         [k.name() for k in query.fetch(_BIG_ENOUGH)])

  def testPatchRemoval(self):
    query = db.Query(Item)
    query.filter('x =', 1)
    query.filter('y =', 3)
    query.filter('z <', 2)
    self.CheckQuery(['130', '131'], query)
    # remove patch and try query again
    self._patch.Remove()
    self.assertRaises(datastore_errors.NeedIndexError, query.fetch, _BIG_ENOUGH)
    # simple queries should still work
    query = db.Query(Item)
    query.filter('x =', 1)
    query.filter('y =', 3)

  def testIndexYamlRecording(self):
    composite_query.ClearIndexYaml()
    query = db.Query(Item)
    query.filter('x =', 1)
    query.filter('y =', 2)
    query.order('-z')
    for _ in query.fetch(1):
      pass
    expected = """indexes:

- kind: Item
  properties:
  - name: x
  - name: y
  - name: z
    direction: desc"""
    self.assertEquals(expected, composite_query.GetIndexYaml())


def setUp():
  global _MODULE_SETUP  # pylint: disable-msg=W0603
  if _MODULE_SETUP:
    return
  _MODULE_SETUP = True

  test_util.InitAppHostingApi()

  global _ROOT_ITEM_KEY  # pylint: disable-msg=W0603
  _ROOT_ITEM_KEY = Item(key_name='root_entity')  # pylint: disable-msg=C6409

  # add some data
  for x in range(5):
    for y in range(5):
      for z in range(5):
        name = '%d%d%d' % (x, y, z)
        Item(key_name=name, parent=_ROOT_ITEM_KEY, x=x, y=y, z=z).put()


class IndexYamlTest(unittest.TestCase):
  """Unit tests for the functions that maintain a set of index definitions."""

  def setUp(self):
    # always start with a known state
    common.ClearPersistent(common.PERSIST_INDEX_NAME)
    indexes = set(['foo', 'bar'])
    composite_query._WriteIndexes(indexes)

  def testReadIndexes(self):
    self.assertSetEqual(set(['foo', 'bar']), composite_query._ReadIndexes())

  def testRecordIndex(self):
    composite_query._RecordIndex('baz')
    self.assertSetEqual(set(['foo', 'bar', 'baz']),
                        composite_query._ReadIndexes())

  def testDuplicatesIgnored(self):
    composite_query._RecordIndex('bar')
    self.assertSetEqual(set(['foo', 'bar']),
                        composite_query._ReadIndexes())

  def testClearIndexYaml(self):
    composite_query.ClearIndexYaml()
    self.assertSetEqual(set(), composite_query._ReadIndexes())

  def testGetIndexYaml(self):
    expected = """indexes:

bar

foo"""
    self.assertEquals(expected, composite_query.GetIndexYaml())


if __name__ == '__main__':
  unittest.main()
