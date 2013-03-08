"""Module for accessing github.com projects."""

import base64
import json
import logging
import os
import re
import sys
import traceback

from mimic.__mimic import common

import model
import settings
import shared

from google.appengine.api import urlfetch_errors


_GITHUB_URL_RE = re.compile('^https?://(?:[^/]+.)?github.com/(?:users/)?([^/]+).*$')


def IsGithubURL(url):
  return _GITHUB_URL_RE.match(url)


def _IsAppEnginePythonRepo(name):
  """Determine whether the given repo name is a App Engine Python project.

  Repo names must meet the following conditions:
  - Starts with 'appengine-'
  - Have a 'python' component
  - Not have a 'java' or 'go' component

  Args:
    name: The github repo name.
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

def _GetAppEnginePythonRepos(page):
  """Get list of App Engine Python repos.

  Given a JSON list of repos, return those repo names which appear to be Python
  App Engine repos. This function can parse the contents of:
  https://api.github.com/users/GoogleCloudPlatform/repos

  Args:
    page: the JSON response returned by /users/:user/repos
  """
  r = json.loads(page)
  repos = [(p['name'], p['description'])
           for p in r if _IsAppEnginePythonRepo(p['name'])]
  return repos

def _GetRepoFiles(page):
  """Get list of files in the given repo.

  Args:
    page: the JSON response returned by /repos/:owner/:repo/contents
  """
  r = json.loads(page)
  files = [(f['path'], f['git_url']) for f in r]
  return files

def PopulateTemplates(template_source):
  """Populate gitgub templates.

  Args:
    template_source: The template source entity.

  Returns:
    List of template entities.
  """
  template_source_url = template_source.key.id()
  matcher = _GITHUB_URL_RE.match(template_source_url)
  github_user = matcher.group(1)
  # e.g. https://api.github.com/users/GoogleCloudPlatform/repos
  url = 'https://api.github.com/users/{0}/repos'.format(github_user)
  page = shared.Fetch(url, follow_redirects=True).content
  candidate_repos = _GetAppEnginePythonRepos(page)

  if common.IsDevMode():
    # fetch fewer templates during development
    candidate_repos = candidate_repos[:1]

  samples = []
  for (repo_name, repo_description) in candidate_repos:
    # e.g. https://github.com/GoogleCloudPlatform/appengine-crowdguru-python
    end_user_repo_url = 'https://github.com/{0}/{1}'.format(github_user, repo_name)
    # e.g. https://api.github.com/repos/GoogleCloudPlatform/appengine-crowdguru-python/contents/
    repo_contents_url = 'https://api.github.com/repos/{0}/{1}/contents/'.format(github_user, repo_name)
    s = model.Template(parent=template_source.key,
                       id=repo_contents_url,
                       name=repo_name,
                       url=end_user_repo_url,
                       description=repo_description or end_user_repo_url)
    samples.append(s)
  model.ndb.put_multi(samples)


# TODO: fetch remote files once in a task, not on every project creation
def PopulateProjectFromGithub(tree, repo_contents_url):
  """Populate project from github template."""
  tree.Clear()

  # e.g. https://api.github.com/repos/GoogleCloudPlatform/appengine-24hrsinsf-python/contents/
  page = shared.Fetch(repo_contents_url, follow_redirects=True).content
  files = _GetRepoFiles(page)
  rpcs = []
  for (path, file_git_url) in files:
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
      formatted_exception = traceback.format_exception(exc_info[0], exc_info[1],
                                                       exc_info[2])
      shared.w('Skipping {0} {1}'.format(path, file_git_url))
      for line in [line for line in formatted_exception if line]:
        shared.w(line)
