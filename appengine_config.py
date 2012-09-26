import re

from __mimic import datastore_tree
from __mimic import mimic


mimic_CREATE_TREE_FUNC = datastore_tree.DatastoreTree

mimic_PROJECT_NAME_COOKIE = '_bliss_project'

mimic_PROJECT_NAME_FROM_PATH_INFO_RE = re.compile('/bliss/p/(.+?)/')


urlfetch_tree_SOURCE_CODE_APP_ID = 'try-appengine'


def namespace_manager_default_namespace_for_request():
  return mimic.GetNamespace()
