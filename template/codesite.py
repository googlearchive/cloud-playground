"""Module for accessing code.google.com projects."""

import os
import re
import sys
import traceback

from mimic.__mimic import common

import fetcher
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
    fetched = fetcher.Fetcher(baseurl, follow_redirects=True)
    page = fetched.content
    candidate_repos = self._GetChildPaths(page)
    fetches = []

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
      fetched = fetcher.Fetcher(app_yaml_url, follow_redirects=True)
      fetches.append((c, project_url, app_yaml_url, fetched))

    for c, project_url, app_yaml_url, fetched in fetches:
      try:
        shared.i('found app.yaml: {}'.format(app_yaml_url))
        name = c.rstrip('/') or project_url
        description = 'Sample code from {0}'.format(project_url)
        model.CreateRepoAsync(owner=model.GetPublicTemplateOwner(),
                              repo_url=project_url,
                              html_url=project_url,
                              name=name,
                              description=description,
                              open_files=[])
      except urlfetch_errors.Error:
        exc_info = sys.exc_info()
        formatted_exception = traceback.format_exception(exc_info[0],
                                                         exc_info[1],
                                                         exc_info[2])
        shared.w('skipping {0}'.format(project_url))
        for line in [line for line in formatted_exception if line]:
          shared.w(line)

  def CreateProjectTreeFromRepo(self, tree, repo):
    repo_url = repo.key.id()

    def AddFiles(dirname):
      url = os.path.join(repo_url, dirname)
      fetched = fetcher.Fetcher(url, follow_redirects=True)
      page = fetched.content
      paths = self._GetChildPaths(page)
      shared.i('{0} -> {1}', url, paths)
      if not paths:
        shared.i('- {0}'.format(dirname))
        tree.SetFile(dirname, page)
      for path in paths:
        if common.GetExtension(path) in settings.SKIP_EXTENSIONS:
          continue
        relpath = os.path.join(dirname, path)
        AddFiles(relpath)

    AddFiles('')
