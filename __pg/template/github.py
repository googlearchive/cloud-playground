"""Module for accessing github.com projects."""

import base64
import re
import sys
import traceback
import yaml

from .. import fetcher
from .. import model
from .. import shared

from . import collection

from google.appengine.api import urlfetch_errors


_GITHUB_URL_RE = re.compile(
    r'^(?:https?|git)://(?:[^/]+.)?github.com/(.+?)(?:\.git)?$'
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

  def RepositoryUrl(self):
    return 'https://api.github.com/repos/{owner}/{repo}'.format(**self.__dict__)

  def BranchesUrl(self):
    if self.branch is None:
      fetched = FetchAsyncWithAuth(self.RepositoryUrl())
      data = fetched.json_content
      self.branch = data['default_branch']
    return ('https://api.github.com/repos/{owner}/{repo}/branches/{branch}'
            .format(**self.__dict__))


def GetInfo(human_url):
  """Get Info object based on the provided github URL.

  For example:
  - https://api.github.com/users/GoogleCloudPlatform/repos
  - https://github.com/GoogleCloudPlatform/appengine-guestbook-python
  - https://github.com/GoogleCloudPlatform/appengine-guestbook-python.git
  - git://github.com/GoogleCloudPlatform/appengine-guestbook-python.git
  - https://github.com/GoogleCloudPlatform/appengine-guestbook-python/tree/part6-staticfiles
  - https://api.github.com/repos/GoogleCloudPlatform/appengine-guestbook-python/branches/part6-staticfiles

  Args:
    human_url: The human readable github.
  Returns:
    The info object.
  """
  matcher = _GITHUB_URL_RE.match(human_url)
  if not matcher:
    return None
  components = matcher.group(1).split('/')
  components.extend([None, None])
  kwargs = {}
  if components[0] in ('users', 'repos'):
    components.pop(0)
  kwargs['user'] = components.pop(0)
  kwargs['repo'] = components.pop(0)
  if components[0] in ('tree', 'branches'):
    components.pop(0)
    kwargs['branch'] = components.pop(0)
  return Info(**kwargs)


def IsValidUrl(url):
  return _GITHUB_URL_RE.match(url)


def FetchAsyncWithAuth(*args, **kwargs):
  credential = model.GetOAuth2Credential('github')
  if credential:
    url_auth_suffix = ('?client_id={0}&client_secret={1}'
                       .format(credential.client_id,
                               credential.client_secret))
  else:
    url_auth_suffix = ''
  return fetcher.Fetcher(*args, url_auth_suffix=url_auth_suffix, **kwargs)


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

  def _GetAppEnginePythonRepos(self, data):
    """Get list of App Engine Python repos.

    Given a list of repos, return those repo names which appear to be
    Python App Engine repos, and which are not in _PROJECT_URL_SKIP_LIST.
    This function can parse the JSON parsed contents of:
    https://api.github.com/users/GoogleCloudPlatform/repos

    Args:
      data: the JSON response returned by
            https://api.github.com/users/{user}/repos

    Returns:
      A list of repos.
    """
    # keys we care about:
    # - html_url, branches_url, name, description, master_branch, owner.login
    repos = [entry for entry in data
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
                  branch=repo['master_branch'])
      branches_url = info.BranchesUrl()
      fetched = FetchAsyncWithAuth(branches_url)
      candidates1.append((repo, fetched))

    # fetch tree url for each repo
    candidates2 = []
    for repo, fetched in candidates1:
      try:
        data = fetched.json_content
      except fetcher.FetchError:
        continue

      # see http://developer.github.com/v3/git/trees/
      tree_url = data['commit']['commit']['tree']['url'] + '?recursive=1'

      fetched = FetchAsyncWithAuth(tree_url)
      candidates2.append((repo, fetched))

    # filter for trees containing 'app.yaml'
    candidates3 = []
    for repo, fetched in candidates2:
      data = fetched.json_content

      app_yaml_urls = [
          entry['url'] for entry in data['tree']
          if entry['path'] == 'app.yaml' and entry['type'] == 'blob'
      ]
      if not app_yaml_urls:
        shared.w('skipping repo due to missing app.yaml: {}'
                 .format(repo['html_url']))
        continue
      fetched = FetchAsyncWithAuth(app_yaml_urls[0])
      candidates3.append((repo, fetched))

    # filter repos whose app.yaml does not contain 'runtime: python27'
    for repo, fetched in candidates3:
      data = fetched.json_content
      base64_content = data['content']
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
    """Populate repos."""
    shared.EnsureRunningInTask()  # gives us automatic retries
    repo_collection_url = self.repo_collection.key.id()
    info = GetInfo(repo_collection_url)
    # e.g. https://api.github.com/users/GoogleCloudPlatform/repos
    url = 'https://api.github.com/users/{0}/repos'.format(info.user)
    fetched = FetchAsyncWithAuth(url, follow_redirects=True)
    repos = self._GetAppEnginePythonRepos(fetched.json_content)

    credential = model.GetOAuth2Credential('github')
    if (not credential or not credential.client_id
        or not credential.client_secret):
      # fetch fewer when we're not authenticated
      repos = repos[:1]

    for repo in repos:
      name = repo['name']
      description = repo['description'] or repo['html_url']
      model.CreateRepoAsync(owner=model.GetPublicTemplateOwner(),
                            repo_url=repo['html_url'],
                            html_url=repo['html_url'],
                            name=name,
                            description=description,
                            show_files=[],
                            read_only_files=[],
                            read_only_demo_url=None)

  def CreateProjectTreeFromRepo(self, tree, repo):
    # e.g. https://github.com/GoogleCloudPlatform/appengine-guestbook-python
    # e.g. https://github.com/GoogleCloudPlatform/appengine-guestbook-python/tree/part6-staticfiles
    html_url = repo.key.id()
    info = GetInfo(html_url)

    # e.g. https://api.github.com/repos/GoogleCloudPlatform/appengine-guestbook-python/branches/part6-staticfiles
    branches_url = info.BranchesUrl()
    fetched = FetchAsyncWithAuth(branches_url)
    data = fetched.json_content

    # see http://developer.github.com/v3/git/trees/
    tree_url = data['commit']['commit']['tree']['url'] + '?recursive=1'
    fetched = FetchAsyncWithAuth(tree_url)
    data = fetched.json_content

    entries = [entry for entry in data['tree'] if entry['type'] == 'blob']
    fetches = []
    for entry in entries:
      fetched = FetchAsyncWithAuth(entry['url'])
      fetches.append((entry, fetched))

    for entry, fetched in fetches:
      try:
        data = fetched.json_content
        base64_content = data['content']
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
