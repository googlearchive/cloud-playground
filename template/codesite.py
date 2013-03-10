"""Module for accessing code.google.com projects."""

import logging
import os
import re
import sys
import traceback

from mimic.__mimic import common

import model
import settings
import shared

from . import collection

from google.appengine.api import urlfetch_errors


_CODESITE_URL_RE = re.compile('^https?://[^/]+.googlecode.com/.+$')

_CODESITE_DIR_FOOTER = ('<em><a href="http://code.google.com/">'
                        'Google Code</a> powered by ')
_CODESITE_DIR_PATH_RE = re.compile('<li><a href="([^"/]+/?)">[^<]+</a></li>')


def IsValidUrl(url):
  return _CODESITE_URL_RE.match(url)


class CodesiteTemplateCollection(collection.TemplateCollection):
  """A class for accessing googlecode repos."""

  def __init__(self, repo_collection):
    super(CodesiteTemplateCollection, self).__init__(repo_collection)

  def _GetChildPaths(self, page):
    if _CODESITE_DIR_FOOTER not in page:
      return []
    paths = _CODESITE_DIR_PATH_RE.findall(page)
    paths = [d for d in paths if not d.startswith('.')]
    return paths

  def PopulateTemplates(self):
    # running in a task gives us automatic retries
    assert 'HTTP_X_APPENGINE_TASKNAME' in os.environ
    baseurl = self.repo_collection.key.id()
    page = shared.Fetch(baseurl, follow_redirects=True).content
    candidates = self._GetChildPaths(page)
    rpcs = []

    # we found a project in the root directory
    if 'app.yaml' in candidates:
      candidates.insert(0, '')

    if common.IsDevMode():
      # fetch fewer templates during development
      candidates = candidates[:3]

    for c in candidates:
      if c and not c.endswith('/'):
        continue
      project_url = '{0}{1}'.format(baseurl, c)
      app_yaml_url = '{0}app.yaml'.format(project_url)
      rpc = shared.Fetch(app_yaml_url, follow_redirects=True, async=True)
      rpcs.append((c, project_url, app_yaml_url, rpc))

    templates = []
    for c, project_url, app_yaml_url, rpc in rpcs:
      try:
        result = rpc.get_result()
        shared.w('{0} {1}'.format(result.status_code, app_yaml_url))
        if result.status_code != 200:
          continue
        description = 'Sample code from {0}'.format(project_url)
        s = model.Template(parent=self.repo_collection.key,
                           id=project_url,
                           name=c.rstrip('/') or project_url,
                           url=project_url,
                           description=description)
        templates.append(s)
      except urlfetch_errors.Error:
        exc_info = sys.exc_info()
        formatted_exception = traceback.format_exception(exc_info[0],
                                                         exc_info[1],
                                                         exc_info[2])
        shared.w('Skipping %s' % project_url)
        for line in [line for line in formatted_exception if line]:
          shared.w(line)
    model.ndb.put_multi(templates)

  # TODO: fetch remote files once in a task, not on every project creation
  def PopulateProjectFromTemplateUrl(self, tree, base_url):
    tree.Clear()

    def add_files(dirname):
      url = os.path.join(base_url, dirname)
      page = shared.Fetch(url, follow_redirects=True).content
      paths = self._GetChildPaths(page)
      shared.w('{0} -> {1}', url, paths)
      if not paths:
        logging.info('- %s', dirname)
        tree.SetFile(dirname, page)
      for path in paths:
        if common.GetExtension(path) in settings.SKIP_EXTENSIONS:
          continue
        relpath = os.path.join(dirname, path)
        add_files(relpath)

    add_files('')
