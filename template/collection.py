"""Class representing a code repository."""

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
    template_project = repo.project.get()
    tree = common.config.CREATE_TREE_FUNC(str(template_project.key.id()))
    self.CreateProjectTreeFromRepo(tree, repo)
    repo.task_is_running = False
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
