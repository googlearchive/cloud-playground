"""Class representing a code repository."""


import json

from .. import model
from .. import shared

from mimic.__mimic import common


_PLAYGROUND_SETTINGS_FILENAME = '.playground'


class RepoCollection(object):
  """An abstract base class for accessing a collection of code repositories."""

  def __init__(self, repo_collection):
    """Constructor.

    Args:
      repo_collection: The repo collection entity.
    """
    self.repo_collection = repo_collection

  def CreateTemplateProject(self, repo):
    shared.EnsureRunningInTask()  # gives us automatic retries
    task_name = shared.GetCurrentTaskName()
    template_project = model.SetProjectOwningTask(repo.project, task_name)
    tree = common.config.CREATE_TREE_FUNC(str(template_project.key.id()))
    tree.Clear()
    self.CreateProjectTreeFromRepo(tree, repo)
    self.ParseAndApplyProjectSettings(tree, template_project)
    template_project = model.SetProjectOwningTask(repo.project, None)
    repo.in_progress_task_name = None
    repo.put()

  def ParseAndApplyProjectSettings(self, tree, project):
    try:
      json_text = tree.GetFileContents(_PLAYGROUND_SETTINGS_FILENAME)
    except IOError:
      shared.i('No {} file found for project {} based on {}'
               .format(_PLAYGROUND_SETTINGS_FILENAME, project.key.id(),
                       project.template_url))
      return
    if not json_text:
      return
    try:
      data = json.loads(json_text)
    except Exception, e:
      shared.w('Failed to parse JSON in {} for project {} based on {} due to {}'
               .format(_PLAYGROUND_SETTINGS_FILENAME, project.key.id(),
                       project.template_url, e))
      return
    model.UpdateProject(project.key.id(), data)


  def PopulateRepos(self):
    """Populate repos for this collection."""
    raise NotImplementedError

  def CreateProjectTreeFromRepo(self, tree, repo):
    """Populate project from code repository.

    Args:
      tree: The Tree to populate.
      repo: The Repo entity.
    """
    raise NotImplementedError
