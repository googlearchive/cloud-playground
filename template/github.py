"""Module for accessing github.com projects."""

import base64
import httplib
import json
import re
import sys
import traceback
import yaml

from mimic.__mimic import common

import model
import shared

from . import collection

from google.appengine.api import urlfetch_errors


_GITHUB_URL_RE = re.compile(
    '^https?://(?:[^/]+.)?github.com/(?:users/)?([^/]+)/?([^/]+)?.*$'
)

# projects which should not be shown in the cloud playground by default
_PROJECT_URL_SKIP_LIST = [
    # Java users only
    'https://github.com/GoogleCloudPlatform/appengine-enable-remote-api-python',
    # (deprecated) master/slave apps only
    'https://github.com/GoogleCloudPlatform/appengine-recover-unapplied-writes-python',
]


def IsValidUrl(url):
  return _GITHUB_URL_RE.match(url)


def FetchWithAuth(*args, **kwargs):
  credential = model.GetOAuth2Credential('github')
  if credential:
    query_str = ('?client_id={0}&client_secret={1}'
                 .format(credential.client_id,
                         credential.client_secret))
    # tuple is immutable
    args = list(args)
    args[0] += query_str
  return shared.Fetch(*args, **kwargs)


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
    Python App Engine repos, and which are not in _PROJECT_URL_SKIP_LIST.
    This function can parse the contents of:
    https://api.github.com/users/GoogleCloudPlatform/repos

    Args:
      page: the JSON response returned by /users/:user/repos

    Returns:
      A list of repos.
    """
    r = json.loads(page)
    # keys we care about: html_url, contents_url, name, description, owner.login
    repos = [entry for entry in r
             if self._IsAppEnginePythonRepo(entry['name'])
                and entry['html_url'] not in _PROJECT_URL_SKIP_LIST]

    candidates1 = []
    for repo in repos:
      # only proceed with repos which look like App Engine Python projects
      if not self._IsAppEnginePythonRepo(repo['name']):
        continue

      # e.g. https://api.github.com/repos/GoogleCloudPlatform/appengine-crowdguru-python/contents/app.yaml
      app_yaml_contents_url = repo['contents_url'].replace('{+path}',
                                                           'app.yaml')
      rpc = FetchWithAuth(app_yaml_contents_url, async=True)
      candidates1.append((rpc, app_yaml_contents_url, repo))

    # filter repos with no app.yaml
    candidates2 = []
    for rpc, app_yaml_contents_url, repo in candidates1:
      result = rpc.get_result()
      if result.status_code != httplib.OK:
        shared.w('skipping repo due to {} fetching {}'
                 .format(result.status_code, app_yaml_contents_url))
        continue
      r = json.loads(result.content)
      app_yaml_git_url = r['git_url']
      rpc = FetchWithAuth(app_yaml_git_url, async=True)
      candidates2.append((rpc, app_yaml_contents_url, app_yaml_git_url, repo))

    # filter repos whose app.yaml does not contain 'runtime: python27'
    repos = []
    for rpc, app_yaml_contents_url, app_yaml_git_url, repo in candidates2:
      result = rpc.get_result()
      r = json.loads(result.content)
      base64_content = r['content']
      decoded_content = base64.b64decode(base64_content)
      config = yaml.safe_load(decoded_content)
      runtime = config.get('runtime')
      if runtime != 'python27':
        shared.w('skipping "runtime: {}" app {}'.format(runtime,
                                                        app_yaml_contents_url))
        continue
      repos.append(repo)

    return repos

  def _GetRepoContents(self, repo_contents_url):
    """Get list of files/directories in the given repo.

    Args:
      page: the JSON response returned by /repos/:owner/:repo/contents

    Returns:
      The list of files/directories.
    """
    page = FetchWithAuth(repo_contents_url, follow_redirects=True).content
    r = json.loads(page)
    entries = []
    for entry in r:
      if entry['type'] == 'dir':
        entries.extend(self._GetRepoContents(entry['url']))
      elif entry['type'] == 'file':
        entries.append((entry['path'], entry['git_url']))
    return entries

  def PopulateRepos(self):
    shared.EnsureRunningInTask()  # gives us automatic retries
    repo_collection_url = self.repo_collection.key.id()
    matcher = _GITHUB_URL_RE.match(repo_collection_url)
    github_user = matcher.group(1)
    # e.g. https://api.github.com/users/GoogleCloudPlatform/repos
    url = 'https://api.github.com/users/{0}/repos'.format(github_user)
    rpc_result = FetchWithAuth(url, follow_redirects=True)
    page = rpc_result.content
    repos = self._GetAppEnginePythonRepos(page)

    credential = model.GetOAuth2Credential('github')
    if (not credential or not credential.client_id
        or not credential.client_secret):
      # fetch fewer when we're not authenticated
      repos = repos[:1]

    repo_entities = []
    for repo in repos:
      name = repo['name']
      description=repo['description'] or repo['html_url']
      model.CreateRepoAsync(repo['html_url'], end_user_url=repo['html_url'],
                            name=name, description=description)

  def CreateProjectTreeFromRepo(self, tree, repo):
    # e.g. https://github.com/GoogleCloudPlatform/appengine-crowdguru-python
    end_user_repo_url = repo.key.id()
    matcher = _GITHUB_URL_RE.match(end_user_repo_url)
    github_user = matcher.group(1)
    repo_name = matcher.group(2)
    # e.g. https://api.github.com/repos/GoogleCloudPlatform/appengine-crowdguru-python/contents/
    repo_contents_url = ('https://api.github.com/repos/{0}/{1}/contents/'
                         .format(github_user, repo_name))

    entries = self._GetRepoContents(repo_contents_url)

    rpcs = []
    for (path, file_git_url) in entries:
      rpc = FetchWithAuth(file_git_url, follow_redirects=True, async=True)
      rpcs.append((file_git_url, path, rpc))

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
        shared.w('skipping {0} {1}'.format(path, file_git_url))
        for line in [line for line in formatted_exception if line]:
          shared.w(line)
