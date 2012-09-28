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

"""A mutable tree implementation that is backed by URL Fetch."""


import httplib
import json

from __mimic import common

import shared

from google.appengine.api import lib_config
from google.appengine.api import urlfetch


_config = lib_config.register('urlfetch_tree', {
    'SOURCE_CODE_APP_ID': None,
    })


class UrlFetchTree(common.Tree):
  """An implementation of Tree backed by URL Fetch."""

  def __init__(self, project_name=None):
    self.project_name = project_name

  def __repr__(self):
    return ('<{0} project_name={1}>'
            .format(self.__class__.__name__, self.project_name))

  @staticmethod
  def _NormalizeDirectoryPath(path):
    """Normalize non empty str to have a trailing '/'."""
    if path and path[-1] != '/':
      return path + '/'
    return path

  def IsMutable(self):
    return True

  def _GetFile(self, path):
    url = ('http://{0}.appspot.com/bliss/p/{1}/getfile/{2}'
           .format(_config.SOURCE_CODE_APP_ID,
                   self.project_name,
                   path))
    headers = {}
    if common.IsDevMode():
      cookie = '{0}={1}'.format(common.config.PROJECT_NAME_COOKIE,
                                self.project_name)
      headers['Cookie'] = cookie
    resp = urlfetch.fetch(url, headers=headers, method='GET',
                          follow_redirects=False, deadline=3)
    return resp

  def _PutFile(self, path, content):
    url = ('http://{0}.appspot.com/bliss/p/{1}/putfile/{2}'
           .format(_config.SOURCE_CODE_APP_ID,
                   self.project_name,
                   path))
    headers = {}
    if common.IsDevMode():
      cookie = '{0}={1}'.format(common.config.PROJECT_NAME_COOKIE,
                                self.project_name)
      headers['Cookie'] = cookie
    resp = urlfetch.fetch(url, headers=headers, method='PUT', payload=content,
                          follow_redirects=False, deadline=3)
    if resp.status_code != httplib.OK:
      shared.e('{0} status code during HTTP PUT on {1}'
               .format(resp.status_code, url))
    return resp

  def GetFileContents(self, path):
    resp = self._GetFile(path)
    if resp.status_code != httplib.OK:
      return None
    return resp.content

  def GetFileSize(self, path):
    contents = self.GetFileContents(path)
    if contents is None:
      return None
    return len(contents)

  def HasFile(self, path):
    # root always exists, even if there are no files in the datastore
    if path == '':  # pylint: disable-msg=C6403
      return True
    resp = self._GetFile(path)
    if resp.status_code == httplib.OK:
      return True
    return False

  def MoveFile(self, path, newpath):
    url = ('http://{0}.appspot.com/bliss/p/{1}/movefile/{2}?newpath={3}'
           .format(_config.SOURCE_CODE_APP_ID,
                   self.project_name,
                   path,
                   newpath))
    headers = {}
    if common.IsDevMode():
      cookie = '{0}={1}'.format(common.config.PROJECT_NAME_COOKIE,
                                self.project_name)
      headers['Cookie'] = cookie
    resp = urlfetch.fetch(url, headers=headers, method='POST',
                          follow_redirects=False, deadline=3)
    if resp.status_code != httplib.OK:
      shared.e('{0} status code during HTTP POST on {1}'
               .format(resp.status_code, url))
    return True

  def DeletePath(self, path):
    url = ('http://{0}.appspot.com/bliss/p/{1}/deletepath/{2}'
           .format(_config.SOURCE_CODE_APP_ID,
                   self.project_name,
                   path))
    headers = {}
    if common.IsDevMode():
      cookie = '{0}={1}'.format(common.config.PROJECT_NAME_COOKIE,
                                self.project_name)
      headers['Cookie'] = cookie
    resp = urlfetch.fetch(url, headers=headers, method='POST',
                          follow_redirects=False, deadline=3)
    if resp.status_code != httplib.OK:
      shared.e('{0} status code during HTTP POST on {1}'
               .format(resp.status_code, url))
    return True

  def Clear(self):
    self.DeletePath('')

  def SetFile(self, path, contents):
    resp = self._PutFile(path, contents)
    assert resp.status_code == httplib.OK

  def HasDirectory(self, path):
    raise NotImplementedError

  def ListDirectory(self, path):
    path = self._NormalizeDirectoryPath(path)
    url = ('http://{0}.appspot.com/bliss/p/{1}/listfiles/'
           .format(_config.SOURCE_CODE_APP_ID,
                   self.project_name))
    headers = {}
    if common.IsDevMode():
      cookie = '{0}={1}'.format(common.config.PROJECT_NAME_COOKIE,
                                self.project_name)
      headers['Cookie'] = cookie
    resp = urlfetch.fetch(url, headers=headers, method='GET',
                          follow_redirects=False, deadline=3)
    if resp.status_code != httplib.OK:
      shared.e('{0} status code during HTTP GET on {1}'
               .format(resp.status_code, url))
    files = json.loads(resp.content)
    paths = set()
    for p in files:
      # 'path is None' means get all files recursively
      if path is None:
        paths.add(p)
        continue
      if not p.startswith(path):
        continue
      tail = p[len(path):]
      # return tail if tail is a file otherwise return dir name (=first segment)
      subpath = tail.split('/', 1)[0]
      paths.add(subpath)
    return sorted(paths)
