"""Class representing a code repository."""

import model
import shared

from mimic.__mimic import common


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
    template_project = model.SetProjectOwningTask(repo.project, None)
    repo.in_progress_task_name = None
    repo.put()

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
