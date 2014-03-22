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

"""An inmutable tree implementation that is backed by ZIP download."""


import cStringIO
import datetime
import httplib
import json
import urllib
import zipfile

from mimic.__mimic import common

from error import Abort
from . import settings
from . import shared

from google.appengine.api import urlfetch


class ZipUrlFetchTree(common.Tree):
  """An implementation of Tree backed by ZIP download via URL Fetch."""

  def __init__(self, namespace, access_key):
    if not namespace:
      Abort(httplib.FORBIDDEN, 'Missing namespace')
    if not access_key:
      Abort(httplib.FORBIDDEN, 'Missing access key')
    super(ZipUrlFetchTree, self).__init__(namespace, access_key)
    self.namespace = namespace
    self.access_key = access_key

    path_info = '{}/zip'.format(common.CONTROL_PREFIX)
    query_params = '{}={}&use_basepath=false'.format(
      common.config.PROJECT_ID_QUERY_PARAM, namespace)
    playground_hostname = (settings.PLAYGROUND_USER_CONTENT_HOST or
                           settings.PLAYGROUND_HOSTS[0])
    url = 'https://{}{}?{}'.format(playground_hostname, path_info, query_params)

    result = shared.Fetch(access_key, url, method='GET', deadline=30, retries=3)
    buf = cStringIO.StringIO(result.content)
    self._zipfile = zipfile.ZipFile(buf)

  def __repr__(self):
    return ('<{0} namespace={1!r}>'
            .format(self.__class__.__name__, self.namespace))

  def IsMutable(self):
    return False

  def GetFileContents(self, path):
    if path not in self._zipfile.namelist():
      return None
    with self._zipfile.open(path) as f:
      return f.read()

  def GetFileSize(self, path):
    if path not in self._zipfile.namelist():
      return 0
    return self._zipfile.getinfo(path).file_size

  def GetFileLastModified(self, path):
    dt = self._zipfile.getinfo(path).date_time
    return datetime.datetime(*dt)

  def HasFile(self, path):
    # root always exists, even if there are no files in the tree
    if path == '':  # pylint: disable-msg=C6403
      return True
    return path in self._zipfile.namelist()

  def HasDirectory(self, path):
    path = self._NormalizeDirectoryPath(path)
    for p in self._zipfile.namelist():
      if p.startswith(path):
        return True
    return False

  def ListDirectory(self, path):
    path = self._NormalizeDirectoryPath(path)
    paths = [p for p in self._zipfile.namelist() if p.startswith(path)]
    return sorted(paths)
