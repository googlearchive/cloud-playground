"""Class representing a code repository."""

import os


class RepoCollection(object):
  """An abstract base class for accessing a collection of code repositories."""

  def __init__(self, repo_collection):
    """Constructor.

    Args:
      repo_collection: The repo collection entity.
    """
    self.repo_collection = repo_collection

  def IsValidUrl(self, url):
    """Determines whether the given URL is valid for this code repository."""
    return False

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
