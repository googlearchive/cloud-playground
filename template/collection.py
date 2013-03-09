"""Class representing a code repository."""


class TemplateCollection(object):
  """An abstract base class for accessing a tree of files."""

  def __init__(self, template_source):
    """Constructor.

    Args:
      template_source: The template source entity.
    """
    self.template_source = template_source

  def IsValidUrl(self, url):
    """Determines whether the given URL is valid for this code repository."""
    return False

  def PopulateTemplates(self):
    """Populate gitgub templates."""
    raise NotImplementedError

  def PopulateProjectFromTemplate(self, tree, template):
    """Populate project from template.

    Args:
      tree: The file tree to populate.
      template: The template entity.
    """
    raise NotImplementedError
