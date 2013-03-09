"""Module for accessing github.com projects."""

import json
import logging
import os

from mimic.__mimic import common

import model
import settings

from . import template_collection

from google.appengine.ext import ndb


_PLAYGROUND_JSON = '__playground.json'


def IsValidUrl(url):
  return url.startswith(settings.TEMPLATE_PROJECT_DIR)


class FilesystemTemplateCollection(template_collection.TemplateCollection):
  """A class for accessing github repos."""

  def __init__(self, template_source):
    super(FilesystemTemplateCollection, self).__init__(template_source)

  def PopulateTemplates(self):
    templates = []
    template_dir = self.template_source.key.id()
    for dirname in os.listdir(template_dir):
      dirpath = os.path.join(template_dir, dirname)
      if not os.path.isdir(dirpath):
        continue
      try:
        f = open(os.path.join(dirpath, _PLAYGROUND_JSON))
        data = json.loads(f.read())
        name = data.get('template_name')
        description = data.get('template_description')
      except IOError:
        name = dirname
        description = dirname
      url = ('https://code.google.com/p/cloud-playground/source/browse'
             '?repo=bliss#git%2Ftemplates%2F' + dirname)
      t = model.Template(parent=self.template_source.key,
                         id=os.path.join(template_dir, dirname),  # url
                         name=name,
                         url=url,
                         description=description)
      templates.append(t)
      ndb.put_multi(templates)

  def PopulateProjectFromTemplateUrl(self, tree, template_url):
    tree.Clear()

    def add_files(dirname):
      for path in os.listdir(os.path.join(template_url, dirname)):
        if path == _PLAYGROUND_JSON:
          continue
        if common.GetExtension(path) in settings.SKIP_EXTENSIONS:
          continue
        relpath = os.path.join(dirname, path)
        fullpath = os.path.join(template_url, dirname, path)
        if os.path.isdir(fullpath):
          add_files(relpath)
        else:
          with open(fullpath, 'rb') as f:
            logging.info('- %s', relpath)
            tree.SetFile(relpath, f.read())

    add_files('')
