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
from google.appengine.ext import deferred


_CODESITE_URL_RE = re.compile('^https?://[^/]+.googlecode.com/.+$')

_CODESITE_DIR_FOOTER = ('<em><a href="http://code.google.com/">'
                        'Google Code</a> powered by ')
_CODESITE_DIR_PATH_RE = re.compile('<li><a href="([^"/]+/?)">[^<]+</a></li>')


def IsValidUrl(url):
  return _CODESITE_URL_RE.match(url)


class CodesiteRepoCollection(collection.RepoCollection):
  """A class for accessing googlecode code repositories."""

  def __init__(self, repo_collection):
    super(CodesiteRepoCollection, self).__init__(repo_collection)

  def _GetChildPaths(self, page):
    if _CODESITE_DIR_FOOTER not in page:
      return []
    paths = _CODESITE_DIR_PATH_RE.findall(page)
    paths = [d for d in paths if not d.startswith('.')]
    return paths

  def PopulateRepos(self):
    shared.EnsureRunningInTask()  # gives us automatic retries
    baseurl = self.repo_collection.key.id()
    page = shared.Fetch(baseurl, follow_redirects=True).content
    candidate_repos = self._GetChildPaths(page)
    rpcs = []

    # we found a project in the root directory
    if 'app.yaml' in candidate_repos:
      candidate_repos.insert(0, '')

    if common.IsDevMode():
      # fetch fewer repos during development
      candidate_repos = candidate_repos[:1]

    for c in candidate_repos:
      if c and not c.endswith('/'):
        continue
      project_url = '{0}{1}'.format(baseurl, c)
      app_yaml_url = '{0}app.yaml'.format(project_url)
      rpc = shared.Fetch(app_yaml_url, follow_redirects=True, async=True)
      rpcs.append((c, project_url, app_yaml_url, rpc))

    repos = []
    for c, project_url, app_yaml_url, rpc in rpcs:
      try:
        result = rpc.get_result()
        shared.w('{0} {1}'.format(result.status_code, app_yaml_url))
        if result.status_code != 200:
          continue
        name = c.rstrip('/') or project_url
        description = 'Sample code from {0}'.format(project_url)
        repo = model.CreateRepo(project_url, name=name, description=description)
        repos.append(repo)
      except urlfetch_errors.Error:
        exc_info = sys.exc_info()
        formatted_exception = traceback.format_exception(exc_info[0],
                                                         exc_info[1],
                                                         exc_info[2])
        shared.w('Skipping {0}'.format(project_url))
        for line in [line for line in formatted_exception if line]:
          shared.w(line)
    model.ndb.put_multi(repos)
    for repo in repos:
      deferred.defer(self.CreateTemplateProject, repo.key)

  def CreateProjectTreeFromRepo(self, tree, repo):
    repo_url = repo.key.id()
    tree.Clear()

    def add_files(dirname):
      url = os.path.join(repo_url, dirname)
      page = shared.Fetch(url, follow_redirects=True).content
      paths = self._GetChildPaths(page)
      shared.w('{0} -> {1}', url, paths)
      if not paths:
        logging.info('- {0}'.format(dirname))
        tree.SetFile(dirname, page)
      for path in paths:
        if common.GetExtension(path) in settings.SKIP_EXTENSIONS:
          continue
        relpath = os.path.join(dirname, path)
        add_files(relpath)

    add_files('')
