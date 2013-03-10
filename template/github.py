"""Module for accessing github.com projects."""

import base64
import json
import re
import sys
import traceback

from mimic.__mimic import common

import model
import shared

from . import collection

from google.appengine.api import urlfetch_errors


_GITHUB_URL_RE = re.compile(
    '^https?://(?:[^/]+.)?github.com/(?:users/)?([^/]+).*$'
)


def IsValidUrl(url):
  return _GITHUB_URL_RE.match(url)


class GithubRepoCollection(collection.RepoCollection):
  """A class for accessing github code repositories."""

  def __init__(self, repo_collection):
    super(GithubRepoCollection, self).__init__(repo_collection)

  def _IsAppEnginePythonRepo(self, name):
    """Determine whether the given repo name is an App Engine Python project.

    Repo names must meet the following conditions:
    - Starts with 'appengine-'
    - Have a 'python' component
    - Not have a 'java' or 'go' component

    Args:
      name: The github repo name.

    Returns:
      True if the given repo name is an App Engine Python Project.
    """
    name = name.lower()
    if not name.startswith('appengine-'):
      return False
    words = name.split('-')
    if 'python' not in words:
      return False
    if 'java' in words or 'go' in words:
      return False
    return True

  def _GetAppEnginePythonRepos(self, page):
    """Get list of App Engine Python repos.

    Given a JSON list of repos, return those repo names which appear to be
    Python App Engine repos. This function can parse the contents of:
    https://api.github.com/users/GoogleCloudPlatform/repos

    Args:
      page: the JSON response returned by /users/:user/repos

    Returns:
      A list of repos.
    """
    r = json.loads(page)
    repos = [(p['name'], p['description'])
             for p in r if self._IsAppEnginePythonRepo(p['name'])]
    return repos

  def _GetRepoFiles(self, page):
    """Get list of files in the given repo.

    Args:
      page: the JSON response returned by /repos/:owner/:repo/contents

    Returns:
      The list files.
    """
    r = json.loads(page)
    files = [(f['path'], f['type'], f['git_url']) for f in r]
    return files

  def PopulateTemplates(self):
    shared.EnsureRunningInTask()  # gives us automatic retries
    repo_collection_url = self.repo_collection.key.id()
    matcher = _GITHUB_URL_RE.match(repo_collection_url)
    github_user = matcher.group(1)
    # e.g. https://api.github.com/users/GoogleCloudPlatform/repos
    url = 'https://api.github.com/users/{0}/repos'.format(github_user)
    page = shared.Fetch(url, follow_redirects=True).content
    candidate_repos = self._GetAppEnginePythonRepos(page)

    if common.IsDevMode():
      # fetch fewer repo during development
      candidate_repos = candidate_repos[:1]

    repos = []
    for (repo_name, repo_description) in candidate_repos:
      # e.g. https://github.com/GoogleCloudPlatform/appengine-crowdguru-python
      end_user_repo_url = ('https://github.com/{0}/{1}'
                           .format(github_user, repo_name))
      # e.g. https://api.github.com/repos/GoogleCloudPlatform/appengine-crowdguru-python/contents/
      repo_contents_url = ('https://api.github.com/repos/{0}/{1}/contents/'
                           .format(github_user, repo_name))
      repo = model.Repo(parent=self.repo_collection.key,
                        id=repo_contents_url,
                        name=repo_name,
                        url=end_user_repo_url,
                        description=repo_description or end_user_repo_url)
      repos.append(repo)
    model.ndb.put_multi(repos)

  # TODO: fetch remote files once in a task, not on every project creation
  def PopulateProjectFromTemplateUrl(self, tree, repo_contents_url):
    tree.Clear()

    # e.g. https://api.github.com/repos/GoogleCloudPlatform/appengine-24hrsinsf-python/contents/
    page = shared.Fetch(repo_contents_url, follow_redirects=True).content
    files = self._GetRepoFiles(page)

    if common.IsDevMode():
      # fetch fewer files during development
      files = files[:1]

    rpcs = []
    for (path, entry_type, file_git_url) in files:
      # skip 'dir' entries
      if entry_type != 'file':
        continue
      rpc = shared.Fetch(file_git_url, follow_redirects=True, async=True)
      rpcs.append((file_git_url, path, rpc))

    files = []
    for file_git_url, path, rpc in rpcs:
      try:
        result = rpc.get_result()
        shared.w('{0} {1} {2}'.format(result.status_code, path, file_git_url))
        if result.status_code != 200:
          continue
        r = json.loads(result.content)
        base64_content = r['content']
        decoded_content = base64.b64decode(base64_content)
        tree.SetFile(path, decoded_content)
      except urlfetch_errors.Error:
        exc_info = sys.exc_info()
        formatted_exception = traceback.format_exception(exc_info[0],
                                                         exc_info[1],
                                                         exc_info[2])
        shared.w('Skipping {0} {1}'.format(path, file_git_url))
        for line in [line for line in formatted_exception if line]:
          shared.w(line)
