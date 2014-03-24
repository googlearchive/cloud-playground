"""App Engine configuration file."""

import json
import os
import re
import sys


from mimic.__mimic import common
from mimic.__mimic import datastore_tree

from __pg import appids
from __pg import settings
from __pg import zip_urlfetch_tree

from google.appengine.api import app_identity


def _FixupSysPath():
  """Add additional directories to sys.path."""
  app_root_dir = os.path.dirname(__file__)
  for dir_name in ('lib', 'api-python-client'):
    dir_path = os.path.join(app_root_dir, 'api-python-client')
    if dir_path not in sys.path:
      sys.path.append(dir_path)


_FixupSysPath()

# our current app id
app_id = app_identity.get_application_id()

# pylint: disable-msg=invalid-name
if common.IsDevMode() or app_id == appids.PLAYGROUND_APP_ID:
  mimic_CREATE_TREE_FUNC = datastore_tree.DatastoreTree
else:
  mimic_CREATE_TREE_FUNC = zip_urlfetch_tree.ZipUrlFetchTree

mimic_JSON_ENCODER = json.JSONEncoder()
mimic_JSON_ENCODER.indent = 4
mimic_JSON_ENCODER.sort_keys = True

mimic_NAMESPACE = '_playground'

# keep in sync with app/js/controllers.js
mimic_PROJECT_ID_QUERY_PARAM = '_mimic_project'

mimic_PROJECT_ID_FROM_PATH_INFO_RE = re.compile('/playground/p/(.+?)/')

if common.IsDevMode():
  scheme = 'http'
else:
  scheme = 'https'

if settings.PLAYGROUND_USER_CONTENT_HOST:
  mimic_ALLOWED_USER_CONTENT_HOSTS = [settings.PLAYGROUND_USER_CONTENT_HOST]
else:
  mimic_ALLOWED_USER_CONTENT_HOSTS = None

mimic_CORS_ALLOWED_ORIGINS = ['{0}://{1}'.format(scheme, h)
                              for h in settings.PLAYGROUND_HOSTS]

mimic_CORS_ALLOWED_HEADERS = ','.join([
    'Accept',
    'Content-Type'
    'Origin',
    'X-Requested-With',
    'X-XSRF-Token',
])

# # see the SDK's sample_appengine_config.py
# appstats_DATASTORE_DETAILS = True
# appstats_CALC_RPC_COSTS = True
#
# def webapp_add_wsgi_middleware(app):
#   from google.appengine.ext.appstats import recording
#   app = recording.appstats_wsgi_middleware(app)
#   return app
