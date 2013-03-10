"""Class representing a code repository."""

import os

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

  def CreateTemplateProject(self, repo_key):
    shared.EnsureRunningInTask()  # gives us automatic retries
    repo = repo_key.get()
    user = model.GetAnonymousUser()
    template_url = repo.key.id()
    name = repo.name
    description = repo.description
    tp = model.CreateProject(user, template_url, name, description)
    tree = common.config.CREATE_TREE_FUNC(str(tp.key.id()))
    self.PopulateProjectFromRepo(tree, repo)


  def PopulateRepos(self):
    """Populate repos for this collection."""
    raise NotImplementedError

  def PopulateProjectFromRepo(self, tree, repo):
    """Populate project from code repository.

    Args:
      tree: The Tree to populate.
      repo: The Repo entity.
    """
    raise NotImplementedError
