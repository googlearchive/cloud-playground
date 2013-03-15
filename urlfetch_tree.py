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
import urllib

from mimic.__mimic import common

import settings
import shared

from google.appengine.api import urlfetch


_URL_FETCH_DEADLINE = 6


class UrlFetchTree(common.Tree):
  """An implementation of Tree backed by URL Fetch."""

  def __init__(self, namespace=''):
    super(UrlFetchTree, self).__init__(namespace)
    self.namespace = namespace

  def __repr__(self):
    return ('<{0} namespace={1!r}>'
            .format(self.__class__.__name__, self.namespace))

  @staticmethod
  def _NormalizeDirectoryPath(path):
    """Normalize non empty str to have a trailing '/'."""
    if path and path[-1] != '/':
      return path + '/'
    return path

  def _ToFileURL(self, control_path, params):
    params = params.copy()
    params[common.config.PROJECT_ID_QUERY_PARAM] = self.namespace
    return ('https://{0}/_ah/mimic/{1}?{2}'
            .format(settings.PLAYGROUND_USER_CONTENT_HOST,
                    control_path,
                    urllib.urlencode(params)))

  def IsMutable(self):
    return True

  def RemoteGetFile(self, path):
    """Retrieve the file via URL Fetch.

    Args:
      path: The file path.

    Returns:
      The URL Fetch response.
    """
    url = self._ToFileURL('file', {'path': path})
    headers = {}
    if common.IsDevMode():
      cookie = '{0}={1}'.format(common.config.PROJECT_NAME_COOKIE,
                                self.namespace)
      headers['Cookie'] = cookie
    resp = urlfetch.fetch(url, headers=headers, method='GET',
                          follow_redirects=False, deadline=_URL_FETCH_DEADLINE)
    return resp

  def RemotePutFile(self, path, content):
    """Put the file via URL Fetch.

    Args:
      path: The file path.
      content: The file contents.

    Returns:
      The URL Fetch response.
    """
    url = self._ToFileURL('file', {'path': path})
    headers = {}
    if common.IsDevMode():
      cookie = '{0}={1}'.format(common.config.PROJECT_NAME_COOKIE,
                                self.namespace)
      headers['Cookie'] = cookie
    resp = urlfetch.fetch(url, headers=headers, method='PUT', payload=content,
                          follow_redirects=False,
                          deadline=_URL_FETCH_DEADLINE)
    if resp.status_code != httplib.OK:
      shared.e('{0} status code during HTTP PUT on {1}'
               .format(resp.status_code, url))
    return resp

  def GetFileContents(self, path):
    resp = self.RemoteGetFile(path)
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
    resp = self.RemoteGetFile(path)
    if resp.status_code == httplib.OK:
      return True
    return False

  def MoveFile(self, path, newpath):
    """Rename a file.

    Args:
      path: The file path to rename.
      newpath: The new path.

    Returns:
      True if the move succeeded.
    """
    url = self._ToFileURL('file', {'path': path, 'newpath': newpath})
    headers = {}
    if common.IsDevMode():
      cookie = '{0}={1}'.format(common.config.PROJECT_NAME_COOKIE,
                                self.namespace)
      headers['Cookie'] = cookie
    resp = urlfetch.fetch(url, headers=headers, method='POST',
                          follow_redirects=False, deadline=_URL_FETCH_DEADLINE)
    if resp.status_code != httplib.OK:
      shared.e('{0} status code during HTTP POST on {1}'
               .format(resp.status_code, url))
    return True

  def DeletePath(self, path):
    """Delete a file or directory.

    Args:
      path: The path to delete.

    Returns:
      True if the delete succeeded.
    """
    url = self._ToFileURL('delete', {'path': path})
    headers = {}
    if common.IsDevMode():
      cookie = '{0}={1}'.format(common.config.PROJECT_NAME_COOKIE,
                                self.namespace)
      headers['Cookie'] = cookie
    resp = urlfetch.fetch(url, headers=headers, method='POST',
                          follow_redirects=False, deadline=_URL_FETCH_DEADLINE)
    if resp.status_code != httplib.OK:
      shared.e('{0} status code during HTTP POST on {1}'
               .format(resp.status_code, url))
    return True

  def Clear(self):
    self.DeletePath('')

  def SetFile(self, path, contents):
    resp = self.RemotePutFile(path, contents)
    assert resp.status_code == httplib.OK

  def HasDirectory(self, path):
    return bool(self.ListDirectory(path))

  def ListDirectory(self, path):
    """List the current directory or tree contents.

    Args:
      path: The directory path to list or '' to access the entire tree.

    Returns:
      A list of files in the specified directory or tree.
    """
    path = self._NormalizeDirectoryPath(path)
    url = self._ToFileURL('dir', {})
    headers = {}
    if common.IsDevMode():
      cookie = '{0}={1}'.format(common.config.PROJECT_NAME_COOKIE,
                                self.namespace)
      headers['Cookie'] = cookie
    resp = urlfetch.fetch(url, headers=headers, method='GET',
                          follow_redirects=False, deadline=_URL_FETCH_DEADLINE)
    if resp.status_code != httplib.OK:
      shared.e('{0} status code during HTTP GET on {1}'
               .format(resp.status_code, url))
    files = json.loads(resp.content)
    paths = set()
    for f in files:
      candidate_path = f['path']
      # 'path is None' means get all files recursively
      if path is None:
        paths.add(candidate_path)
        continue
      if not candidate_path.startswith(path):
        continue
      tail = candidate_path[len(path):]
      # return tail if tail is a file otherwise return dir name (=first segment)
      subpath = tail.split('/', 1)[0]
      paths.add(subpath)
    return sorted(paths)
