"""Module containing the datastore mode and associated functions."""

import json
import logging
import os
import random

import codesite
import error
import settings
import shared

from google.appengine.api import memcache
from google.appengine.ext import ndb


_PLAYGROUND_JSON = '__playground.json'

# 10 minutes
_MEMCACHE_TIME = 3600

# tuples containing templates (uri, description)
_TEMPLATE_SOURCES = [
    ('templates/',
     'Playground Templates'),
    ('https://google-app-engine-samples.googlecode.com/svn/trunk/',
     'Python App Engine Samples'),
    ('https://google-app-engine-samples.googlecode.com/svn/trunk/python27/',
     'Python 2.7 App Engine Samples'),
]


class _AhGlobal(ndb.Model):
  """A Model used to store the root entity for global configuration data.

  A single root entity allows us to use ancestor queries for consistency.
  """
  pass


class _AhBlissUser(ndb.Model):
  """A Model to store bliss users."""
  projects = ndb.KeyProperty(repeated=True, indexed=False)


class _AhBlissProject(ndb.Model):
  """A Model to store bliss projects."""
  project_description = ndb.StringProperty(indexed=False)
  writers = ndb.StringProperty(repeated=True)

  @property
  def project_name(self):
    return self.key.id()


class _AhTemplateSource(ndb.Model):
  """A Model to represent a project template source.

  The base url is used as the entity key id.
  """
  description = ndb.StringProperty(indexed=False)

  @property
  def base_url(self):
    return self.key.id()


class _AhTemplate(ndb.Model):
  """A Model to store project templates and metadata.

  This Model has _AhTemplateSource as its parent and uses
  the template url as the entity key id.
  """
  name = ndb.StringProperty(indexed=False)
  description = ndb.StringProperty(indexed=False)

  @property
  def template_url(self):
    return self.key.id()


def GetUser(user_id):
  return _AhBlissUser.get_or_insert(user_id,
                                    namespace=settings.BLISS_NAMESPACE)


def GetProjects(user):
  projects = ndb.get_multi(user.projects)
  # assert users.projects does not reference proejcts which do not exist
  assert None not in projects, (
      'Missing project(s): %s' %
      [key for (key, prj) in zip(user.projects, projects) if prj is None])
  return projects


def GetProject(project_name):
  return _AhBlissProject.get_by_id(project_name)


def GetGlobalRootEntity():
  return _AhGlobal.get_or_insert('config', namespace=settings.BLISS_NAMESPACE)


def GetTemplateSources():
  """Get template sources."""
  _MEMCACHE_KEY = _AhTemplateSource.__class__.__name__
  sources = memcache.get(_MEMCACHE_KEY)
  if sources:
    return sources
  sources = _AhTemplateSource.query(ancestor=GetGlobalRootEntity().key).fetch()
  if not sources:
    sources = _GetTemplateSources()
  sources.sort(key=lambda source: source.description)
  memcache.set(_MEMCACHE_KEY, sources, time=_MEMCACHE_TIME)
  return sources


def _GetTemplateSources():
  sources = []
  for uri, description in _TEMPLATE_SOURCES:
    source = _AhTemplateSource(id=uri, parent=GetGlobalRootEntity().key,
                               description=description)
    sources.append(source)
  ndb.put_multi(sources)
  return sources


def GetTemplates(template_source):
  """Get templates from a given template source."""
  _MEMCACHE_KEY = '{0}-{1}'.format(_AhTemplate.__class__.__name__,
                                   template_source)
  templates = memcache.get(_MEMCACHE_KEY)
  templates = None



  if templates:
    return templates
  templates = (_AhTemplate.query(ancestor=template_source.key)
               .order(_AhTemplate.key).fetch())
  if not templates:
    templates = _GetTemplates(template_source)
  templates.sort(key=lambda template: template.name.lower())
  memcache.set(_MEMCACHE_KEY, templates, time=_MEMCACHE_TIME)
  return templates


def _GetTemplates(template_source):
  url = template_source.key.id()
  if url == 'templates/':
    return _GetFileSystemTemplates(template_source)
  elif codesite.IsCodesiteURL(url):
    return codesite.GetTemplates(template_source)
  else:
    shared.e('Unknown URL template %s' % url)


def _GetFileSystemTemplates(template_source):
  templates = []
  template_dir = template_source.key.id()
  for dirname in os.listdir(template_dir):
    try:
      f = open(os.path.join(template_dir, dirname, _PLAYGROUND_JSON))
      data = json.loads(f.read())
      name = data.get('template_name')
      description = data.get('template_description')
    except IOError:
      name = dirname
      description = dirname
    t = _AhTemplate(parent=template_source.key,
                    id=os.path.join(template_dir, dirname),  # url
                    name=name,
                    description=description)
    templates.append(t)
  return templates


def DeleteTemplates():
  query = _AhTemplateSource.query(ancestor=GetGlobalRootEntity().key)
  source_keys = query.fetch(keys_only=True)
  keys = []
  for k in source_keys:
    keys.append(k)
    template_keys = _AhTemplate.query(ancestor=k).fetch(keys_only=True)
    keys.extend(template_keys)
  ndb.delete_multi(keys)
  memcache.flush_all()


def NewProjectName():
  return 'foo{0}'.format(random.randint(100, 999))


@ndb.transactional(xg=True)
def CreateProject(user, project_name, project_description):
  """Create a new user project.

  Args:
    user: The user for which the project is to be created.
    project_name: The project name.
    project_description: The project description.

  Returns:
    The new project entity.

  Raises:
    BlissError: If the project name already exists.
  """
  prj = _AhBlissProject.get_by_id(project_name)
  if prj:
    raise error.BlissError('Project name %s already exists' % project_name)
  prj = _AhBlissProject(id=project_name,
                        project_description=project_description,
                        writers=[user.key.id()])
  prj.put()
  user.projects.append(prj.key)
  user.put()
  return prj


def PopulateProjectWithTemplate(tree, template_url):
  """Populate a project from a template."""
  tree.Clear()

  def add_files(dirname):
    for path in os.listdir(os.path.join(template_url, dirname)):
      if path == _PLAYGROUND_JSON:
        continue
      if shared.GetExtension(path) in settings.SKIP_EXTENSIONS:
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


def DeleteProject(user, tree, project_name):
  """Delete an existing project."""
  assert tree
  assert project_name
  # 1. delete files
  tree.Clear()

  @ndb.transactional(xg=True)
  def del_project():
    # 2. delete project
    prj = GetProject(project_name)
    prj.key.delete()
    # 3. delete project references
    user.projects.remove(prj.key)
    user.put()

  del_project()
