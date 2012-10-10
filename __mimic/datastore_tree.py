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

"""A mutable tree implementation that is backed by Datastore."""




from __mimic import common

from google.appengine.ext import ndb


# TODO: Unfortunately this model will pollute the target application's
# Datastore.  The name (prefixed with _Ah) was chosen to minimize collision,
# but there may be a better mechanism.
class _AhMimicFile(ndb.Model):
  """A Model to store file contents in Datastore.

  The file's path should be used as the key for the entity.
  """
  # allow admin console changes to become immediately visible
  _use_memcache = False

  contents = ndb.BlobProperty(required=True)
  udpated = ndb.DateTimeProperty(auto_now=True)


class DatastoreTree(common.Tree):
  """An implementation of Tree backed by Datastore."""

  def __init__(self, project_name=None):
    if project_name:
      namespace = project_name
    else:
      namespace = None
    # Having a root entity key allows us to use ancestor queries for strong
    # consistency in the High Replication Datastore
    self.root = ndb.Key(_AhMimicFile, '/', namespace=namespace)

  def __repr__(self):
    return '<{0} root={1}>'.format(self.__class__.__name__, self.root)

  @staticmethod
  def _NormalizeDirectoryPath(path):
    """Normalize non empty str to have a trailing '/'."""
    if path and path[-1] != '/':
      return path + '/'
    return path

  def IsMutable(self):
    return True

  def GetFileContents(self, path):
    entity = _AhMimicFile.get_by_id(path, parent=self.root)
    if entity is None:
      return None
    return entity.contents

  def GetFileSize(self, path):
    contents = self.GetFileContents(path)
    if contents is None:
      return None
    return len(contents)

  def HasFile(self, path):
    # root always exists, even if there are no files in the datastore
    if path == '':  # pylint: disable-msg=C6403
      return True
    entity = _AhMimicFile.get_by_id(path, parent=self.root)
    return entity is not None

  @ndb.transactional(xg=True)
  def MoveFile(self, path, newpath):
    entity = _AhMimicFile.get_by_id(path, parent=self.root)
    if entity is None:
      return False
    self.SetFile(newpath, entity.contents)
    entity.key.delete()
    return True

  def DeletePath(self, path):
    normpath = self._NormalizeDirectoryPath(path)
    keys = _AhMimicFile.query(ancestor=self.root).fetch(keys_only=True)
    keys = [k for k in keys if k.id() == path or k.id().startswith(normpath)]
    if not keys:
      return False
    ndb.delete_multi(keys)
    return True

  def Clear(self):
    keys = _AhMimicFile.query(ancestor=self.root).fetch(keys_only=True)
    ndb.delete_multi(keys)

  def SetFile(self, path, contents):
    entity = _AhMimicFile(id=path, parent=self.root, contents=contents)
    entity.put()

  def HasDirectory(self, path):
    path = self._NormalizeDirectoryPath(path)
    # always return True for root, even if tree is empty
    if path == '/':
      return True
    for key in _AhMimicFile.query(ancestor=self.root).iter(keys_only=True):
      if key.id().startswith(path):
        return True
    return False

  def ListDirectory(self, path):
    path = self._NormalizeDirectoryPath(path)
    paths = set()
    # TODO: optimize by using a more structured tree representation
    keys = _AhMimicFile.query(ancestor=self.root).iter(keys_only=True)
    for key in keys:
      entry_path = key.id()
      # 'path is None' means get all files recursively
      if path is None:
        paths.add(entry_path)
        continue
      if not entry_path.startswith(path):
        continue
      tail = entry_path[len(path):]
      # return tail if tail is a file otherwise return dir name (=first segment)
      subpath = tail.split('/', 1)[0]
      paths.add(subpath)
    return sorted(paths)
