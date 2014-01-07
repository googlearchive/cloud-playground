"""Module for accessing github.com projects."""

import json
import os
import urllib

from mimic.__mimic import common

from .. import model
from .. import settings
from .. import shared

from . import collection


_PLAYGROUND_SETTINGS_FILENAME = '.playground'


def IsValidUrl(url):
  return url.startswith(settings.TEMPLATE_PROJECT_DIR)


class FilesystemRepoCollection(collection.RepoCollection):
  """A class for accessing file system code repositories."""

  def __init__(self, repo_collection):
    super(FilesystemRepoCollection, self).__init__(repo_collection)

  def PopulateRepos(self):
    shared.EnsureRunningInTask()  # gives us automatic retries
    template_dir = self.repo_collection.key.id()  # repo_collection_url
    for dirname in os.listdir(template_dir):
      dirpath = os.path.join(template_dir, dirname)
      if not os.path.isdir(dirpath):
        continue
      try:
        with open(os.path.join(dirpath, _PLAYGROUND_SETTINGS_FILENAME)) as f:
          data = json.loads(f.read())
        name = data.get('template_name')
        description = data.get('template_description')
        show_files = data.get('show_files', [])
        orderby = data.get('orderby')
      except IOError:
        name = dirpath
        description = dirname
        show_files = []
        orderby = None
      url = os.path.join(template_dir, dirname)
      html_url = ('https://code.google.com/p/cloud-playground/source/browse/'
                  '?repo=bliss#git%2F{}'.format(urllib.quote(url)))
      model.CreateRepoAsync(owner=model.GetPublicTemplateOwner(),
                            repo_url=url,
                            html_url=html_url,
                            name=name,
                            description=description,
                            show_files=show_files,
                            orderby=orderby)

  def CreateProjectTreeFromRepo(self, tree, repo):
    repo_url = repo.key.id()

    def AddFiles(dirname):
      for path in os.listdir(os.path.join(repo_url, dirname)):
        if path == _PLAYGROUND_SETTINGS_FILENAME:
          continue
        if common.GetExtension(path) in settings.SKIP_EXTENSIONS:
          continue
        relpath = os.path.join(dirname, path)
        fullpath = os.path.join(repo_url, dirname, path)
        if os.path.isdir(fullpath):
          AddFiles(relpath)
        else:
          try:
            with open(fullpath, 'rb') as f:
              shared.i('- {0}'.format(fullpath))
              tree.SetFile(relpath, f.read())
          except IOError:
            # file access may be disallowed due to app.yaml skip_files
            shared.w('skipping {}'.format(fullpath))

    AddFiles('')
