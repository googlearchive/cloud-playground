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

import error
from error import Abort
import settings
import shared

from google.appengine.api import urlfetch


_URL_FETCH_DEADLINE = 6


class UrlFetchTree(common.Tree):
  """An implementation of Tree backed by URL Fetch."""

  def __init__(self, namespace, access_key):
    if not namespace:
      Abort(httplib.FORBIDDEN, 'Missing namespace')
    if not access_key:
      Abort(httplib.FORBIDDEN, 'Missing access key')
    super(UrlFetchTree, self).__init__(namespace)
    self.namespace = namespace
    self.access_key = access_key

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
    url = '{}/{}?{}'.format(common.CONTROL_PREFIX, control_path,
                            urllib.urlencode(params))
    playground_hostname = (settings.PLAYGROUND_USER_CONTENT_HOST or
                           settings.PLAYGROUND_HOSTS[0])
    url = 'https://{0}{1}'.format(playground_hostname, url)
    return url

  def IsMutable(self):
    return True

  def _Fetch(self, url, method, payload=None):
    headers = {settings.ACCESS_KEY_HTTP_HEADER: self.access_key}
    return urlfetch.fetch(url, headers=headers, method=method, payload=payload,
                          follow_redirects=False, deadline=_URL_FETCH_DEADLINE)

  def RemoteGetFile(self, path):
    """Retrieve the file via URL Fetch.

    Args:
      path: The file path.

    Returns:
      The URL Fetch response.
    """
    url = self._ToFileURL('file', {'path': path})
    return self._Fetch(url, method='GET')

  def RemotePutFile(self, path, content):
    """Put the file via URL Fetch.

    Args:
      path: The file path.
      content: The file contents.

    Returns:
      The URL Fetch response.
    """
    url = self._ToFileURL('file', {'path': path})
    resp = self._Fetch(url, method='PUT', payload=content)
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
    resp = self._Fetch(url, method='POST')
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
    resp = self._Fetch(url, method='POST')
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
    resp = self._Fetch(url, method='GET')
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
