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

"""Tests related to the datastore."""



import unittest

from google.appengine.ext import db


_ITEM_COUNT = 5  # number of items expected in the datastore
_MAX_FETCH = 100  # max number to fetch at once


class Item(db.Model):
  x = db.IntegerProperty()
  y = db.IntegerProperty()


class FileTest(unittest.TestCase):
  def testCompositeQuery(self):
    # this query normally requires a composite index
    query = Item.all()
    query.filter('x =', 1)
    query.order('-y')
    items = list(query.fetch(_MAX_FETCH))
    values = [i.y for i in items]
    self.assertEquals(range(_ITEM_COUNT-1, -1, -1), values)


def setUp():
  query = Item.all()
  query.order('y')
  items = list(query.fetch(_MAX_FETCH))

  # don't need to do anything if items already match expected data
  if [i.y for i in items] == range(_ITEM_COUNT):
    return

  # clear datastore
  while items:
    for item in items:
      item.delete()
    items = list(query.fetch(_MAX_FETCH))

  # populate with new items
  for y in range(_ITEM_COUNT):
    Item(x=1, y=y).put()
