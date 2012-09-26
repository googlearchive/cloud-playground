import re
import urlfetch_tree

from __mimic import mimic
from __mimic import datastore_tree

from google.appengine.api import app_identity

urlfetch_tree_SOURCE_CODE_APP_ID = 'try-appengine'

if app_identity.get_application_id() == urlfetch_tree_SOURCE_CODE_APP_ID:
  mimic_CREATE_TREE_FUNC = datastore_tree.DatastoreTree
else:
  mimic_CREATE_TREE_FUNC = urlfetch_tree.UrlFetchTree

mimic_PROJECT_NAME_COOKIE = '_bliss_project'

mimic_PROJECT_NAME_FROM_PATH_INFO_RE = re.compile('/bliss/p/(.+?)/')

def namespace_manager_default_namespace_for_request():
  return mimic.GetNamespace()
