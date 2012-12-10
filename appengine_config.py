"""App Engine configuration file."""

import re


from __mimic import common
from __mimic import datastore_tree
from __mimic import mimic

import caching_urlfetch_tree
import settings

from google.appengine.api import app_identity


# our current app id
app_id = app_identity.get_application_id()

urlfetch_tree_SOURCE_CODE_APP_ID = settings.PLAYGROUND_APP_ID

if common.IsDevMode() or urlfetch_tree_SOURCE_CODE_APP_ID == app_id:
  mimic_CREATE_TREE_FUNC = datastore_tree.DatastoreTree
else:
  mimic_CREATE_TREE_FUNC = caching_urlfetch_tree.CachingUrlFetchTree

mimic_NAMESPACE = '_playground'

mimic_PROJECT_ID_QUERY_PARAM = '_mimic_project'

mimic_PROJECT_ID_FROM_PATH_INFO_RE = re.compile('/playground/p/(.+?)/')


# pylint: disable-msg=C6409
def namespace_manager_default_namespace_for_request():
  return mimic.GetNamespace()
