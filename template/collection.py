"""Class representing a code repository."""

import os

import model

class RepoCollection(object):
  """An abstract base class for accessing a collection of code repositories."""

  def __init__(self, repo_collection):
    """Constructor.

    Args:
      repo_collection: The repo collection entity.
    """
    self.repo_collection = repo_collection

  def CreateTemplateProject(self, repo_key):
    repo = repo_key.get()
    user = model.GetAnonymousUser()
    template_url = repo.key.id()
    name = repo.name
    description = repo.description
    project = model.CreateProject(user, template_url, name, description)

  def PopulateTemplates(self):
    """Populate templates for this collection."""
    raise NotImplementedError

  def PopulateProjectFromTemplate(self, tree, template):
    """Populate project from template.

    Args:
      tree: The file tree to populate.
      template: The template entity.
    """
    raise NotImplementedError
