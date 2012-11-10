"""Module containing the datastore mode and associated functions."""

import json
import logging
import os
import random

import codesite
import settings
import shared

from google.appengine.api import memcache
from google.appengine.api import taskqueue
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


class Global(ndb.Model):
  """A Model used to store the root entity for global configuration data.

  A single root entity allows us to use ancestor queries for consistency.
  """
  created = ndb.DateTimeProperty(auto_now_add=True, indexed=False)
  updated = ndb.DateTimeProperty(auto_now=True, indexed=False)


class PlaygroundUser(ndb.Model):
  """A Model to store playground users."""
  projects = ndb.KeyProperty(repeated=True, indexed=False)
  created = ndb.DateTimeProperty(auto_now_add=True, indexed=False)
  updated = ndb.DateTimeProperty(auto_now=True, indexed=False)


class PlaygroundProject(ndb.Model):
  """A Model to store playground projects."""
  project_name = ndb.StringProperty(indexed=False)
  project_description = ndb.StringProperty(indexed=False)
  template_url = ndb.StringProperty(indexed=False)
  owner = ndb.StringProperty(required=True)
  writers = ndb.StringProperty(repeated=True)
  created = ndb.DateTimeProperty(auto_now_add=True, indexed=False)
  updated = ndb.DateTimeProperty(auto_now=True, indexed=False)
  orderby = ndb.StringProperty(required=True)

  def _pre_put_hook(self):
    self.orderby = '{0}-{1}'.format(self.owner, self.updated.isoformat())


class TemplateSource(ndb.Model):
  """A Model to represent a project template source.

  The base url is used as the entity key id.
  """
  description = ndb.StringProperty(indexed=False)
  created = ndb.DateTimeProperty(auto_now_add=True, indexed=False)
  updated = ndb.DateTimeProperty(auto_now=True, indexed=False)

  @property
  def base_url(self):
    return self.key.id()


class Template(ndb.Model):
  """A Model to store project templates and metadata.

  This Model has TemplateSource as its parent and uses
  the template url as the entity key id.
  """
  name = ndb.StringProperty(indexed=False)
  description = ndb.StringProperty(indexed=False)
  created = ndb.DateTimeProperty(auto_now_add=True, indexed=False)
  updated = ndb.DateTimeProperty(auto_now=True, indexed=False)

  @property
  def template_url(self):
    return self.key.id()


def GetOrCreateUser(user_id):
  return PlaygroundUser.get_or_insert(user_id,
                                 namespace=settings.PLAYGROUND_NAMESPACE)


def GetProjects(user):
  projects = ndb.get_multi(user.projects)
  # assert users.projects does not reference projects which do not exist
  assert None not in projects, (
      'Missing project(s): %s' %
      [key for (key, prj) in zip(user.projects, projects) if prj is None])
  return projects


def GetProject(project_id):
  project = PlaygroundProject.get_by_id(long(project_id),
                                   namespace=settings.PLAYGROUND_NAMESPACE)
  return project


def RenameProject(project_id, project_name):
   project = GetProject(project_id)
   project.project_name = project_name
   project.put()
   return project


def _UpdateProjectUserKeys(dest_user, source_user):
  projects = GetProjects(source_user)
  dest_user_key = dest_user.key.id()
  source_user_key = source_user.key.id()
  for p in projects:
    if source_user_key not in p.writers:
      continue
    p.writers.remove(source_user_key)
    if dest_user_key in p.writers:
      continue
    p.owner = dest_user_key
    p.writers.append(dest_user_key)
  ndb.put_multi(projects)


def AdoptProjects(dest_user_key, source_user_key):
  dest_user = GetOrCreateUser(dest_user_key)
  source_user = GetOrCreateUser(source_user_key)
  _UpdateProjectUserKeys(dest_user, source_user)
  dest_user.projects.extend(source_user.projects)
  dest_user.put()
  source_user.key.delete()


def GetGlobalRootEntity():
  return Global.get_or_insert('config', namespace=settings.PLAYGROUND_NAMESPACE)


def GetTemplateSource(url):
  return TemplateSource.get_by_id(url, parent=GetGlobalRootEntity().key)


def GetTemplateSources():
  """Get template sources."""
  _MEMCACHE_KEY = TemplateSource.__name__
  sources = memcache.get(_MEMCACHE_KEY, namespace=settings.PLAYGROUND_NAMESPACE)
  if sources:
    return sources
  sources = TemplateSource.query(ancestor=GetGlobalRootEntity().key).fetch()
  if not sources:
    sources = _GetTemplateSources()
  sources.sort(key=lambda source: source.description)
  memcache.set(_MEMCACHE_KEY, sources, namespace=settings.PLAYGROUND_NAMESPACE,
               time=_MEMCACHE_TIME)
  return sources


@ndb.transactional(xg=True)
def _GetTemplateSources():
  sources = []
  for uri, description in _TEMPLATE_SOURCES:
    key = ndb.Key(TemplateSource, uri, parent=GetGlobalRootEntity().key)
    source = key.get()
    # avoid race condition when multiple requests call into this method
    if source:
      continue
    source = TemplateSource(key=key, description=description)
    shared.w('adding task to populate template source {0!r}'.format(uri))
    taskqueue.add(url='/_playground_tasks/template_source/populate',
                  params={'key': source.key.id()})
    sources.append(source)
  ndb.put_multi(sources)
  return sources


def GetTemplates():
  """Get templates from a given template source."""
  _MEMCACHE_KEY = '{0}'.format(Template.__name__)
  templates = memcache.get(_MEMCACHE_KEY,
                           namespace=settings.PLAYGROUND_NAMESPACE)
  if templates:
    return templates
  templates = (Template.query(namespace=settings.PLAYGROUND_NAMESPACE)
               .order(Template.key).fetch())
  templates.sort(key=lambda template: template.name.lower())
  memcache.set(_MEMCACHE_KEY, templates,
               namespace=settings.PLAYGROUND_NAMESPACE, time=_MEMCACHE_TIME)
  return templates


def GetTemplatesBySource(template_source):
  """Get templates from a given template source."""
  _MEMCACHE_KEY = '{0}-{1}'.format(Template.__name__,
                                   template_source.key.id())
  templates = memcache.get(_MEMCACHE_KEY,
                           namespace=settings.PLAYGROUND_NAMESPACE)
  if templates:
    return templates
  templates = (Template.query(ancestor=template_source.key)
               .order(Template.key).fetch())
  templates.sort(key=lambda template: template.name.lower())
  memcache.set(_MEMCACHE_KEY, templates,
               namespace=settings.PLAYGROUND_NAMESPACE, time=_MEMCACHE_TIME)
  return templates


def PopulateFileSystemTemplates(template_source):
  """Populate file system templates.

  Args:
    template_source: The template source entity.
  """
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
    t = Template(parent=template_source.key,
                 id=os.path.join(template_dir, dirname),  # url
                 name=name,
                 description=description)
    templates.append(t)
    ndb.put_multi(templates)


def DeleteTemplates():
  query = TemplateSource.query(ancestor=GetGlobalRootEntity().key)
  source_keys = query.fetch(keys_only=True)
  keys = []
  for k in source_keys:
    keys.append(k)
    template_keys = Template.query(ancestor=k).fetch(keys_only=True)
    keys.extend(template_keys)
  ndb.delete_multi(keys)
  memcache.flush_all()


def NewProjectName():
  return 'foo{0}'.format(random.randint(100, 999))


@ndb.transactional(xg=True)
def CreateProject(user, template_url, project_name, project_description):
  """Create a new user project.

  Args:
    user: The user for which the project is to be created.
    template_url: The template URL to populate the project files or None.
    project_name: The project name.
    project_description: The project description.

  Returns:
    The new project entity.

  Raises:
    PlaygroundError: If the project name already exists.
  """
  prj = PlaygroundProject(project_name=project_name,
                          project_description=project_description,
                          owner=user.key.id(),
                          writers=[user.key.id()],
                          template_url=template_url,
                          namespace=settings.PLAYGROUND_NAMESPACE)
  prj.put()
  user.projects.append(prj.key)
  user.put()
  return prj


def PopulateProject(tree, template_url):
  """Populate project from a template.

  Args:
    tree: A tree object to use to retrieve files.
    template_url: The template URL to populate the project files.
  """
  if codesite.IsCodesiteURL(template_url):
    codesite.PopulateProjectFromCodesite(tree, template_url)
  else:
    _PopulateProjectWithTemplate(tree, template_url)


def _PopulateProjectWithTemplate(tree, template_url):
  """Populate a project from a template.

  Args:
    tree: A tree object to use to retrieve files.
    template_url: The template URL to populate the project files or None.
  """
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


def DeleteProject(user, tree, project_id):
  """Delete an existing project."""
  assert tree
  assert project_id
  # 1. delete files
  tree.Clear()

  @ndb.transactional(xg=True)
  def del_project():
    # 2. get current entities
    usr = user.key.get()
    prj = GetProject(project_id)
    # 3. delete project
    prj.key.delete()
    # 4. delete project references
    usr.projects.remove(prj.key)
    usr.put()

  del_project()
