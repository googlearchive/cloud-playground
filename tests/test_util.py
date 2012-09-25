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

"""Utility functions for tests."""



import os
import shutil
import sys
import tempfile

from google.appengine.api import apiproxy_stub_map
from google.appengine.api import datastore_file_stub
from google.appengine.api import urlfetch_stub
from google.appengine.api.blobstore import blobstore_stub
from google.appengine.api.blobstore import file_blob_storage
from google.appengine.api.files import file_service_stub
from google.appengine.api.memcache import memcache_stub

from google.appengine.datastore import datastore_stub_util

from google.appengine.ext import ndb


# Assert that webapp has not yet been imported by the calling test, since we
# want the 'APPENGINE_RUNTIME' evnironment to be set to 'python27' first.
# We choose to do that below, since all our tests import this module anyway.
if hasattr(sys.modules.get('google.appengine.ext'), 'webapp'):
  raise Exception('%s must be imported before webapp' % __name__)

# Must be set before webapp is imported from google.appengine.ext, since
# google/appengine/ext/webapp/__init__.py uses this to decide whether to import
# from webapp or webapp2.
os.environ['APPENGINE_RUNTIME'] = 'python27'


# Sanity check that we indeed get webapp2, since imports are easy to get wrong.
try:
  from google.appengine.ext import webapp  # pylint: disable-msg=C6204
  assert hasattr(webapp, 'get_app'), 'Not webapp2'
except ImportError:
  # Carry on, test doesn't use webapp.
  pass


def InitAppHostingApi():
  """Initialize stubs for various app hosting APIs."""
  # clear ndb's context cache
  # see https://developers.google.com/appengine/docs/python/ndb/cache
  ndb.get_context().clear_cache()

  # Pretend we're running in the dev_appserver
  os.environ['SERVER_SOFTWARE'] = 'Development/unittests'

  appid = os.environ['APPLICATION_ID'] = 'app'
  apiproxy_stub_map.apiproxy = apiproxy_stub_map.APIProxyStubMap()
  # Need an HRD stub to support XG transactions
  hrd_policy = datastore_stub_util.TimeBasedHRConsistencyPolicy()
  apiproxy_stub_map.apiproxy.RegisterStub(
      'datastore_v3', datastore_file_stub.DatastoreFileStub(
          appid, '/dev/null', '/dev/null', trusted=True,
          require_indexes=True, consistency_policy=hrd_policy))
  # memcache stub
  apiproxy_stub_map.apiproxy.RegisterStub(
      'memcache', memcache_stub.MemcacheServiceStub())
  # urlfetch stub
  apiproxy_stub_map.apiproxy.RegisterStub(
      'urlfetch', urlfetch_stub.URLFetchServiceStub())
  # blobstore stub
  temp_dir = tempfile.gettempdir()
  storage_directory = os.path.join(temp_dir, 'blob_storage')
  if os.access(storage_directory, os.F_OK):
    shutil.rmtree(storage_directory)
  blob_storage = file_blob_storage.FileBlobStorage(
      storage_directory, appid)
  apiproxy_stub_map.apiproxy.RegisterStub(
      'blobstore', blobstore_stub.BlobstoreServiceStub(blob_storage))
  # file stub, required by blobstore stub
  apiproxy_stub_map.apiproxy.RegisterStub(
      'file', file_service_stub.FileServiceStub(blob_storage))


def GetDefaultEnvironment():
  """Function for creating a default CGI environment."""
  return {
      'REQUEST_METHOD': 'GET',
      'wsgi.url_scheme': 'http',
      'SERVER_NAME': 'localhost',
      'SERVER_PORT': '8080',
  }
