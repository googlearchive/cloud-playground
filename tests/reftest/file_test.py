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

"""Tests related to file operations."""



import os
import unittest


class FileTest(unittest.TestCase):
  def testOpen(self):
    a_file = open('foo.txt')
    self.assertEquals('Hello\n', a_file.read())

  def testOpenRelativeToModule(self):
    dir_name = os.path.dirname(__file__)
    file_name = os.path.join(dir_name, 'foo.txt')
    a_file = open(file_name)
    self.assertEquals('Hello\n', a_file.read())

  def testOpenExternal(self):
    a_file = open(__file__)
    self.assertTrue('testOpenExternal' in a_file.read())

  def testFile(self):
    a_file = file('foo.txt')
    self.assertEquals('Hello\n', a_file.read())
    self.assertTrue(isinstance(a_file, file))
