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
    '^https?://(?:[^/]+.)?github.com/(.+)$'
)

# projects which should not be shown in the cloud playground by default
_PROJECT_URL_SKIP_LIST = [
    # Java users only
    'https://github.com/GoogleCloudPlatform/appengine-enable-remote-api-python',
    # (deprecated) master/slave apps only
    'https://github.com/GoogleCloudPlatform/appengine-recover-unapplied-writes-python',
]


# https://api.github.com/
# {
#   "current_user_url": "https://api.github.com/user",
#   "authorizations_url": "https://api.github.com/authorizations",
#   "emails_url": "https://api.github.com/user/emails",
#   "emojis_url": "https://api.github.com/emojis",
#   "events_url": "https://api.github.com/events",
#   "following_url": "https://api.github.com/user/following{/target}",
#   "gists_url": "https://api.github.com/gists{/gist_id}",
#   "hub_url": "https://api.github.com/hub",
#   "issue_search_url": "https://api.github.com/legacy/issues/search/{owner}/{repo}/{state}/{keyword}",
#   "issues_url": "https://api.github.com/issues",
#   "keys_url": "https://api.github.com/user/keys",
#   "notifications_url": "https://api.github.com/notifications",
#   "organization_repositories_url": "https://api.github.com/orgs/{org}/repos/{?type,page,per_page,sort}",
#   "organization_url": "https://api.github.com/orgs/{org}",
#   "public_gists_url": "https://api.github.com/gists/public",
#   "rate_limit_url": "https://api.github.com/rate_limit",
#   "repository_url": "https://api.github.com/repos/{owner}/{repo}",
#   "repository_search_url": "https://api.github.com/legacy/repos/search/{keyword}{?language,start_page}",
#   "current_user_repositories_url": "https://api.github.com/user/repos{?type,page,per_page,sort}",
#   "starred_url": "https://api.github.com/user/starred{/owner}{/repo}",
#   "starred_gists_url": "https://api.github.com/gists/starred",
#   "team_url": "https://api.github.com/teams",
#   "user_url": "https://api.github.com/users/{user}",
#   "user_organizations_url": "https://api.github.com/user/orgs",
#   "user_repositories_url": "https://api.github.com/users/{user}/repos{?type,page,per_page,sort}",
#   "user_search_url": "https://api.github.com/legacy/user/search/{keyword}"
# }

# https://api.github.com/users/GoogleCloudPlatform/repos
# [
#   {
#     "id": 6730561,
#     "name": "appengine-guestbook-python",
#     ...
#     ...
#     "full_name": "GoogleCloudPlatform/appengine-guestbook-python",
#     "html_url": "https://github.com/GoogleCloudPlatform/appengine-guestbook-python",
#     "description": "Guestbook is an example application showing basic usage of Google App Engine",
#     "url": "https://api.github.com/repos/GoogleCloudPlatform/appengine-guestbook-python",
#     "branches_url": "https://api.github.com/repos/GoogleCloudPlatform/appengine-guestbook-python/branches{/branch}",
#     "tags_url": "https://api.github.com/repos/GoogleCloudPlatform/appengine-guestbook-python/tags{/tag}",
#     "trees_url": "https://api.github.com/repos/GoogleCloudPlatform/appengine-guestbook-python/git/trees{/sha}",
#     "contents_url": "https://api.github.com/repos/GoogleCloudPlatform/appengine-guestbook-python/contents/{+path}",
#     "git_url": "git://github.com/GoogleCloudPlatform/appengine-guestbook-python.git",
#     "homepage": "https://developers.google.com/appengine/docs/python/gettingstartedpython27/",
#     "language": "Python",
#     "master_branch": "master",
#     "default_branch": "master"
#   }
# ]
class Info(object):

  def __init__(self, user, repo=None, branch=None, path=''):
    self.user = self.owner = user
    self.repo = repo
    self.branch = branch
    self.path = path

  def repository_url(self):
    return 'https://api.github.com/repos/{owner}/{repo}'.format(**self.__dict__)

  def branches_url(self):
    if self.branch == None:
      result = FetchWithAuth(self.repository_url(), async=False)
      r = json.loads(result.content)
      self.branch = r['master_branch']
    return ('https://api.github.com/repos/{owner}/{repo}/branches/{branch}'
            .format(**self.__dict__))


def GetInfo(html_url):
  """Get Info object based on the provided HTML URL.

  For example:
  - https://api.github.com/users/GoogleCloudPlatform/repos
  - https://github.com/GoogleCloudPlatform/appengine-guestbook-python
  - https://github.com/GoogleCloudPlatform/appengine-guestbook-python/tree/part6-staticfiles
  """
  matcher = _GITHUB_URL_RE.match(html_url)
  if not matcher:
    return None
  components = matcher.group(1).split('/')
  components.extend([None, None])
  kwargs = {}
  if components[0] == 'users':
    components.pop(0)
  kwargs['user'] = components.pop(0)
  kwargs['repo'] = components.pop(0)
  if components[0] == 'tree':
    components.pop(0)
    kwargs['branch'] = components.pop(0)
  return Info(**kwargs)


def IsValidUrl(url):
  return _GITHUB_URL_RE.match(url)


def FetchWithAuth(*args, **kwargs):
  credential = model.GetOAuth2Credential('github')
  if credential:
    query_str = ('?client_id={0}&client_secret={1}'
                 .format(credential.client_id,
                         credential.client_secret))
    # convert immutable tuple to mutable list
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
      page: the JSON response returned by
            https://api.github.com/users/{user}/repos

    Returns:
      A list of repos.
    """
    r = json.loads(page)
    # keys we care about:
    # - html_url, branches_url, name, description, master_branch, owner.login
    repos = [entry for entry in r
             if self._IsAppEnginePythonRepo(entry['name'])
                and entry['html_url'] not in _PROJECT_URL_SKIP_LIST]

    # fetch master_branch url for each repo
    candidates1 = []
    for repo in repos:
      # only proceed with repos which look like App Engine Python projects
      if not self._IsAppEnginePythonRepo(repo['name']):
        shared.w('skipping non App Engine Python repo {}'
                 .format(repo['html_url']))
        continue

      info = Info(user=repo['owner']['login'], repo=repo['name'],
                  branch=entry['master_branch'])
      branches_url = info.branches_url()
      rpc = FetchWithAuth(branches_url, async=True)
      candidates1.append((repo, rpc))

    # fetch tree url for each repo
    candidates2 = []
    for repo, rpc in candidates1:
      result = rpc.get_result()
      if result.status_code != 200:
        continue
      r = json.loads(result.content)

      # see http://developer.github.com/v3/git/trees/
      tree_url = r['commit']['commit']['tree']['url'] + '?recursive=1'

      rpc = FetchWithAuth(tree_url, async=True)
      candidates2.append((repo, rpc))

    # filter for trees containing 'app.yaml'
    candidates3 = []
    for repo, rpc in candidates2:
      result = rpc.get_result()
      if result.status_code != 200:
        continue
      r = json.loads(result.content)

      contains_app_yaml = False
      app_yaml_urls = [
          entry['url'] for entry in r['tree']
          if entry['path'] == 'app.yaml' and entry['type'] == 'blob'
      ]
      if not app_yaml_urls:
        shared.w('skipping repo due to missing app.yaml: {}'
                 .format(repo['html_url']))
        continue
      rpc = FetchWithAuth(app_yaml_urls[0], async=True)
      candidates3.append((repo, rpc))

    # filter repos whose app.yaml does not contain 'runtime: python27'
    candidates4 = []
    for repo, rpc in candidates3:
      result = rpc.get_result()
      if result.status_code != 200:
        continue
      r = json.loads(result.content)
      base64_content = r['content']
      decoded_content = base64.b64decode(base64_content)
      config = yaml.safe_load(decoded_content)
      runtime = config.get('runtime')
      if runtime != 'python27':
        shared.w('skipping repo due to "runtime: {}" app {}'
                 .format(runtime, repo['html_url']))
        continue
      repos.append(repo)

    return repos

  def PopulateRepos(self):
    shared.EnsureRunningInTask()  # gives us automatic retries
    repo_collection_url = self.repo_collection.key.id()
    info = GetInfo(repo_collection_url)
    # e.g. https://api.github.com/users/GoogleCloudPlatform/repos
    url = 'https://api.github.com/users/{0}/repos'.format(info.user)
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
    # e.g. https://github.com/GoogleCloudPlatform/appengine-guestbook-python
    # e.g. https://github.com/GoogleCloudPlatform/appengine-guestbook-python/tree/part6-staticfiles
    html_url = repo.key.id()
    info = GetInfo(html_url)

    # e.g. https://api.github.com/repos/GoogleCloudPlatform/appengine-guestbook-python/branches/part6-staticfiles
    branches_url = info.branches_url()
    #rpc = FetchWithAuth(branches_url, async=False)
    #result = rpc.get_result()
    #if result.status_code != 200:
    #  raise RuntimeError('http error {}'.format(result.status_code))
    result = FetchWithAuth(branches_url, async=False)
    r = json.loads(result.content)

    # see http://developer.github.com/v3/git/trees/
    tree_url = r['commit']['commit']['tree']['url'] + '?recursive=1'
    #rpc = FetchWithAuth(tree_url, async=False)
    #result = rpc.get_result()
    #if result.status_code != 200:
    #  raise RuntimeError('http error {}'.format(result.status_code))
    #r = json.loads(result.content)
    result = FetchWithAuth(tree_url, async=False)
    r = json.loads(result.content)

    entries = [entry for entry in r['tree'] if entry['type'] == 'blob']
    rpcs = []
    for entry in entries:
      rpc = FetchWithAuth(entry['url'], async=True)
      rpcs.append((entry, rpc))

    for entry, rpc in rpcs:
      try:
        result = rpc.get_result()
        shared.w('{0} {1} {2}'.format(result.status_code, entry['path'], entry['url']))
        if result.status_code != 200:
          continue
        r = json.loads(result.content)
        base64_content = r['content']
        decoded_content = base64.b64decode(base64_content)
        tree.SetFile(entry['path'], decoded_content)
      except urlfetch_errors.Error:
        exc_info = sys.exc_info()
        formatted_exception = traceback.format_exception(exc_info[0],
                                                         exc_info[1],
                                                         exc_info[2])
        shared.w('skipping {0} {1}'.format(entry['path'], entry['url']))
        for line in [line for line in formatted_exception if line]:
          shared.w(line)
