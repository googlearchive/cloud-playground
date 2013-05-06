"""Module containing the datastore mode and associated functions."""

import random

from mimic.__mimic import common

import settings
import shared

from google.appengine.api import memcache
from google.appengine.api import taskqueue
from google.appengine.ext import ndb


class Global(ndb.Model):
  """A Model used to store the root entity for global configuration data.

  A single root entity allows us to use ancestor queries for consistency.
  """
  created = ndb.DateTimeProperty(required=True, auto_now_add=True,
                                 indexed=False)
  updated = ndb.DateTimeProperty(required=True, auto_now=True, indexed=False)


class OAuth2Credential(ndb.Model):
  """A Model to store OAuth2 credentials."""
  client_id = ndb.StringProperty(required=True, indexed=False)
  client_secret = ndb.StringProperty(required=True, indexed=False)


class PlaygroundProject(ndb.Model):
  """A Model to store playground projects."""
  project_name = ndb.StringProperty(required=True, indexed=False)
  project_description = ndb.StringProperty(required=True, indexed=False)
  template_url = ndb.StringProperty(required=True, indexed=False)
  end_user_url = ndb.StringProperty(required=True, indexed=False)
  owner = ndb.StringProperty(required=True)
  writers = ndb.StringProperty(repeated=True)
  created = ndb.DateTimeProperty(required=True, auto_now_add=True,
                                 indexed=False)
  updated = ndb.DateTimeProperty(required=True, auto_now=True, indexed=False)
  in_progress_task_name = ndb.StringProperty(indexed=False)

  @property
  def orderby(self):
    return '{0}-{1}'.format(self.owner, self.updated.isoformat())


def fixit():
  """Method to hold temporary code for data model migrations."""
  pass


class PlaygroundUser(ndb.Model):
  """A Model to store playground users."""
  projects = ndb.KeyProperty(repeated=True, kind=PlaygroundProject,
                             indexed=False)
  created = ndb.DateTimeProperty(required=True, auto_now_add=True,
                                 indexed=False)
  updated = ndb.DateTimeProperty(required=True, auto_now=True, indexed=False)


class RepoCollection(ndb.Model):
  """A Model to represent a collection of code repositories.

  The base url is used as the entity key id.
  """
  description = ndb.StringProperty(required=True, indexed=False)
  created = ndb.DateTimeProperty(required=True, auto_now_add=True,
                                 indexed=False)
  updated = ndb.DateTimeProperty(required=True, auto_now=True, indexed=False)


class Repo(ndb.Model):
  """A Model to represent code repositories.

  This Model uses the repo url as the entity key id.
  """
  name = ndb.StringProperty(required=True, indexed=False)
  description = ndb.StringProperty(required=True, indexed=False)
  end_user_url = ndb.StringProperty(required=True, indexed=False)
  project = ndb.KeyProperty(required=True, kind=PlaygroundProject,
                            indexed=False)
  created = ndb.DateTimeProperty(required=True, auto_now_add=True,
                                 indexed=False)
  updated = ndb.DateTimeProperty(required=True, auto_now=True, indexed=False)
  in_progress_task_name = ndb.StringProperty(indexed=False)


def GetOAuth2Credential(key):
  return OAuth2Credential.get_by_id(key,
                                    namespace=settings.PLAYGROUND_NAMESPACE)


def SetOAuth2Credential(key, client_id, client_secret):
  credential = OAuth2Credential(id=key, client_id=client_id,
                                client_secret=client_secret,
                                namespace=settings.PLAYGROUND_NAMESPACE)
  credential.put()
  return credential


def GetRepo(repo_url):
  return Repo.get_by_id(repo_url, namespace=settings.PLAYGROUND_NAMESPACE)


@ndb.transactional(xg=True)
def CreateRepoAsync(repo_url, end_user_url, name, description):
  repo = GetRepo(repo_url)
  if not repo:
    user = GetTemplateOwner()
    repo = Repo(id=repo_url, end_user_url=end_user_url, name=name,
                description=description,
                namespace=settings.PLAYGROUND_NAMESPACE)
  elif repo.in_progress_task_name:
    raise RuntimeError('repo recreation for {} already executing in task {}'
                       .format(repo_url, repo.in_progress_task_name))
  task = taskqueue.add(queue_name='repo',
                       url='/_playground_tasks/populate_repo',
                       params={'repo_url': repo_url})
  shared.w('task {} added to populate repo {}'.format(task.name, repo_url))
  repo.in_progress_task_name = task.name
  if repo.project:
    SetProjectOwningTask(repo.project, task.name)
  else:
    project = CreateProject(user=user,
                            template_url=repo_url,
                            end_user_url=end_user_url,
                            project_name=name,
                            project_description=description,
                            in_progress_task_name=task.name)
    repo.project = project.key
  repo.put()
  return repo


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


def GetTemplateProjects():
  """Get template projects."""
  user = GetTemplateOwner()
  projects = GetProjects(user)
  return projects


@ndb.transactional(xg=True)
def CopyProject(user, project_id):
  tp = GetProject(project_id)
  project = CreateProject(user=user,
                          template_url=tp.template_url,
                          end_user_url=tp.end_user_url,
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


def _UpdateProjectUserKeys(dst_user, src_user):
  projects = GetProjects(src_user)
  dst_user_key = dst_user.key.id()
  src_user_key = src_user.key.id()
  for p in projects:
    if src_user_key not in p.writers:
      continue
    p.writers.remove(src_user_key)
    if dst_user_key in p.writers:
      continue
    p.owner = dst_user_key
    p.writers.append(dst_user_key)
  ndb.put_multi(projects)


def AdoptProjects(dst_user_key, src_user_key):
  dst_user = GetOrCreateUser(dst_user_key)
  src_user = GetOrCreateUser(src_user_key)
  _UpdateProjectUserKeys(dst_user, src_user)
  dst_user.projects.extend(src_user.projects)
  dst_user.put()
  src_user.key.delete()
  memcache.flush_all()


def GetGlobalRootEntity():
  return Global.get_or_insert('config', namespace=settings.PLAYGROUND_NAMESPACE)


def GetTemplateOwner():
  return GetOrCreateUser('TEMPLATE')


def GetRepoCollection(url):
  return RepoCollection.get_by_id(url, parent=GetGlobalRootEntity().key)


def DeleteReposAndTemplateProjects():
  user = GetTemplateOwner()

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
def CreateProject(user, template_url, end_user_url, project_name,
                  project_description, in_progress_task_name=None):
  """Create a new user project.

  Args:
    user: The user for which the project is to be created.
    template_url: The template URL to populate the project files or None.
    end_user_url: The end user URL to populate the project files or None.
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
                          end_user_url=end_user_url,
                          namespace=settings.PLAYGROUND_NAMESPACE,
                          in_progress_task_name=in_progress_task_name,
                          )
  prj.put()
  # transactional get before update
  user = user.key.get()
  user.projects.append(prj.key)
  user.put()
  return prj


@ndb.transactional()
def SetProjectOwningTask(project_key, in_progress_task_name):
  project = project_key.get()
  if (None not in (in_progress_task_name, project.in_progress_task_name)
      and in_progress_task_name != project.in_progress_task_name):
    raise RuntimeError('illegal project task move {} -> {}'
                       .format(project.in_progress_task_name,
                               in_progress_task_name))
  project.in_progress_task_name = in_progress_task_name
  project.put()
  return project


def GetOrInsertRepoCollection(uri, description):
  return RepoCollection.get_or_insert(uri, description=description,
                                      parent=GetGlobalRootEntity().key)


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
