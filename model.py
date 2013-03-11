"""Module containing the datastore mode and associated functions."""

import json
import os
import random

from mimic.__mimic import common

import settings
import shared

from template import collection

from google.appengine.api import memcache
from google.appengine.ext import ndb


class Global(ndb.Model):
  """A Model used to store the root entity for global configuration data.

  A single root entity allows us to use ancestor queries for consistency.
  """
  created = ndb.DateTimeProperty(auto_now_add=True, indexed=False)
  updated = ndb.DateTimeProperty(auto_now=True, indexed=False)


class OAuth2Credential(ndb.Model):
  """A Model to store OAuth2 credentials."""
  client_id = ndb.StringProperty(indexed=False)
  client_secret = ndb.StringProperty(indexed=False)


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

  @property
  def orderby(self):
    return '{0}-{1}'.format(self.owner, self.updated.isoformat())


class RepoCollection(ndb.Model):
  """A Model to represent a collection of code repositories.

  The base url is used as the entity key id.
  """
  description = ndb.StringProperty(indexed=False)
  created = ndb.DateTimeProperty(auto_now_add=True, indexed=False)
  updated = ndb.DateTimeProperty(auto_now=True, indexed=False)


class Repo(ndb.Model):
  """A Model to represent code repositories.

  This Model uses the repo url as the entity key id.
  """
  name = ndb.StringProperty(indexed=False)
  description = ndb.StringProperty(indexed=False)
  created = ndb.DateTimeProperty(auto_now_add=True, indexed=False)
  updated = ndb.DateTimeProperty(auto_now=True, indexed=False)


def GetOAuth2Credential(key):
  return OAuth2Credential.get_by_id(key,
                                    namespace=settings.PLAYGROUND_NAMESPACE)


def SetOAuth2Credential(key, client_id, client_secret):
  credential = OAuth2Credential(id=key, client_id=client_id,
                                client_secret=client_secret,
                                namespace=settings.PLAYGROUND_NAMESPACE)
  credential.put()
  return credential


def CreateRepo(repo_url, name, description):
  repo = Repo(id=repo_url, name=name, description=description,
              namespace=settings.PLAYGROUND_NAMESPACE)
  repo.put()
  return repo


def GetRepo(repo_url):
  return Repo.get_by_id(repo_url, namespace=settings.PLAYGROUND_NAMESPACE)


def GetOrCreateUser(user_id):
  return PlaygroundUser.get_or_insert(user_id,
                                      namespace=settings.PLAYGROUND_NAMESPACE)


def GetProjects(user):
  projects = ndb.get_multi(user.projects)
  if None in projects:
    # users.projects references projects which do not exist
    missing_projects = [key for (key, prj) in zip(user.projects, projects)
                        if prj is None]
    raise RuntimeError('Missing project(s): {0}'.format(missing_projects))
  return projects


def GetProject(project_id):
  project = PlaygroundProject.get_by_id(long(project_id),
                                        namespace=settings.PLAYGROUND_NAMESPACE)
  return project


@ndb.transactional(xg=True)
def CopyProject(user, project_id):
  tp = GetProject(project_id)
  project = CreateProject(user,
                          template_url=tp.template_url,
                          project_name=tp.project_name,
                          project_description=tp.project_description)
  src_tree = common.config.CREATE_TREE_FUNC(str(tp.key.id()))
  dst_tree = common.config.CREATE_TREE_FUNC(str(project.key.id()))
  paths = src_tree.ListDirectory(None)
  for path in paths:
    if path.endswith('/'):
      continue
    contents = src_tree.GetFileContents(path)
    dst_tree.SetFile(path, contents)
  return project


def RenameProject(project_id, project_name):
  project = GetProject(project_id)
  project.project_name = project_name
  project.put()
  return project


def TouchProject(project_id):
   project = GetProject(project_id)
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
  memcache.flush_all()


def GetGlobalRootEntity():
  return Global.get_or_insert('config', namespace=settings.PLAYGROUND_NAMESPACE)


def GetAnonymousUser():
  return GetOrCreateUser('ANONYMOUS')


def GetRepoCollection(url):
  return RepoCollection.get_by_id(url, parent=GetGlobalRootEntity().key)


def DeleteReposAndTemplateProjects():
  user = GetAnonymousUser()

  # delete template projects
  keys = user.projects
  ndb.delete_multi(keys)

  # delete ANONYMOUS user
  user.key.delete()

  # delete code repositories
  query = Repo.query(namespace=settings.PLAYGROUND_NAMESPACE)
  keys = query.fetch(keys_only=True)
  ndb.delete_multi(keys)

  # delete repo collections
  query = RepoCollection.query(ancestor=GetGlobalRootEntity().key)
  keys = query.fetch(keys_only=True)
  ndb.delete_multi(keys)

  # flush memcache
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
