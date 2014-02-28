"""Module containing the datastore mode and associated functions."""

import os
import random
import time

from mimic.__mimic import common

import datetime
from . import secret
from . import settings
from . import shared

from google.appengine.api import memcache
from google.appengine.api import taskqueue
from google.appengine.api.datastore_types import _MAX_RAW_PROPERTY_BYTES
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


class Project(ndb.Model):
  """A Model to store playground projects."""
  project_name = ndb.StringProperty(required=True, indexed=False)
  project_description = ndb.StringProperty(required=True, indexed=False)
  template_url = ndb.StringProperty(required=True, indexed=False)
  html_url = ndb.StringProperty(required=True, indexed=False)
  owner = ndb.StringProperty(required=True)
  writers = ndb.StringProperty(repeated=True)
  created = ndb.DateTimeProperty(required=True, auto_now_add=True,
                                 indexed=False)
  updated = ndb.DateTimeProperty(required=True, auto_now=True, indexed=False)
  show_files = ndb.StringProperty(required=False, repeated=True, indexed=False)
  read_only_files = ndb.StringProperty(required=False, repeated=True,
                                       indexed=False)
  read_only_demo_url = ndb.StringProperty(required=False, indexed=False)
  orderby = ndb.StringProperty(required=False, indexed=False)
  in_progress_task_name = ndb.StringProperty(indexed=False)
  access_key = ndb.StringProperty(required=True, indexed=False)
  expiration_seconds = ndb.IntegerProperty(required=True, indexed=False)


class User(ndb.Model):
  """A Model to store playground users."""
  projects = ndb.KeyProperty(repeated=True, kind=Project, indexed=False)
  created = ndb.DateTimeProperty(required=True, auto_now_add=True,
                                 indexed=False)
  updated = ndb.DateTimeProperty(required=True, auto_now=True, indexed=False)


class Resource(ndb.Model):
  """A cache for web content.

  The url is used as the entity key.
  """
  etag = ndb.StringProperty(required=True, indexed=False)
  content = ndb.BlobProperty(required=False)
  last_modified = ndb.DateTimeProperty(auto_now=True)


class ResourceChunk(ndb.Model):
  """A model for storing resources > _MAX_RAW_PROPERTY_BYTES."""
  content = ndb.BlobProperty(required=True)


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
  owner = ndb.StringProperty(required=True, indexed=False)
  name = ndb.StringProperty(required=True, indexed=False)
  description = ndb.StringProperty(required=True, indexed=False)
  html_url = ndb.StringProperty(required=True, indexed=False)
  project = ndb.KeyProperty(required=True, kind=Project, indexed=True)
  created = ndb.DateTimeProperty(required=True, auto_now_add=True,
                                 indexed=False)
  updated = ndb.DateTimeProperty(required=True, auto_now=True, indexed=False)
  show_files = ndb.StringProperty(required=False, repeated=True, indexed=False)
  read_only_files = ndb.StringProperty(required=False, repeated=True,
                                       indexed=False)
  read_only_demo_url = ndb.StringProperty(required=False, indexed=False)
  orderby = ndb.StringProperty(required=False, indexed=False)
  in_progress_task_name = ndb.StringProperty(indexed=False)


def GetResource(url):
  """Retrieve a previously stored resource."""
  key = ndb.Key(Resource, url, namespace=settings.PLAYGROUND_NAMESPACE)
  query = ndb.Query(ancestor=key)
  results = query.fetch()
  if not results:
    return None, None
  resource = results[0]
  if resource.content is not None:
    return resource.etag, resource.content
  content = ''
  for resource_chunk in results[1:]:
    content += resource_chunk.content
  return resource.etag, content


def PutResource(url, etag, content):
  """Persist a resource."""
  key = ndb.Key(Resource, url, namespace=settings.PLAYGROUND_NAMESPACE)
  keys = ndb.Query(ancestor=key).fetch(keys_only=True)
  ndb.delete_multi(keys)
  resource = Resource(id=url, etag=etag,
                      namespace=settings.PLAYGROUND_NAMESPACE)
  if len(content) <= _MAX_RAW_PROPERTY_BYTES:
    resource.content = content
    resource.put()
    return
  chunks = [content[i:i + _MAX_RAW_PROPERTY_BYTES]
            for i in range(0, len(content), _MAX_RAW_PROPERTY_BYTES)]
  entities = [ResourceChunk(id=i + 1, parent=resource.key, content=chunks[i])
              for i in range(0, len(chunks))]
  entities.append(resource)
  ndb.put_multi(entities)


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
def CreateRepoAsync(owner, repo_url, html_url, name, description, show_files,
                    read_only_files, read_only_demo_url, orderby=None):
  """Asynchronously create a repo."""
  repo = GetRepo(repo_url)
  if not repo:
    repo = Repo(id=repo_url,
                owner=owner.key.id(),
                html_url=html_url,
                name=name,
                description=description,
                show_files=show_files,
                read_only_files=read_only_files,
                read_only_demo_url=read_only_demo_url,
                orderby=orderby,
                namespace=settings.PLAYGROUND_NAMESPACE)
  elif repo.in_progress_task_name:
    shared.w('ignoring recreation of {} which is already executing in task {}'
             .format(repo_url, repo.in_progress_task_name))
    return
  task = taskqueue.add(queue_name='repo',
                       url='/_playground_tasks/populate_repo',
                       params={'repo_url': repo_url},
                       transactional=True)
  shared.i('task {} added to populate repo {}'.format(task.name, repo_url))
  repo.in_progress_task_name = task.name
  if repo.project:
    SetProjectOwningTask(repo.project, task.name)
  else:
    project = CreateProject(owner=owner,
                            template_url=repo_url,
                            html_url=html_url,
                            project_name=name,
                            project_description=description,
                            show_files=show_files,
                            read_only_files=read_only_files,
                            read_only_demo_url=read_only_demo_url,
                            expiration_seconds=0,
                            orderby=orderby,
                            in_progress_task_name=task.name)
    repo.project = project.key
  repo.put()
  return repo


def GetUser(user_id):
  return User.get_by_id(user_id, namespace=settings.PLAYGROUND_NAMESPACE)


def GetOrCreateUser(user_id):
  return User.get_or_insert(user_id, namespace=settings.PLAYGROUND_NAMESPACE)


def GetProjects(user):
  projects = ndb.get_multi(user.projects)
  if None in projects:
    # users.projects references projects which do not exist
    missing_projects = [key for (key, prj) in zip(user.projects, projects)
                        if prj is None]
    if common.IsDevMode():
      shared.e('Missing project(s): {0}'.format(missing_projects))
    else:
      shared.w('Missing project(s): {0}'.format(missing_projects))
      projects = [p for p in projects if p is not None]
  return projects


def GetProject(project_id):
  try:
    project_id = long(project_id)
  except ValueError:
    return None
  project = Project.get_by_id(project_id,
                              namespace=settings.PLAYGROUND_NAMESPACE)
  return project


def GetPublicTemplateProjects():
  """Get template projects."""
  user = GetPublicTemplateOwner()
  projects = GetProjects(user)
  return projects


def _CreateProjectTree(project):
  return common.config.CREATE_TREE_FUNC(str(project.key.id()))


def CopyProject(owner, template_project, expiration_seconds,
                new_project_name=None):
  """Create new a project from a template.

  Args:
    owner: The user for which the project is to be created.
    template_project: The template project to be copied.
    expiration_seconds: Number of seconds before project is deleted.
    new_project_name: The new project's name, or None to use "Copy of ..." based
        on the template.

  Returns:
    A new project.
  """
  expiration_seconds = expiration_seconds or settings.DEFAULT_EXPIRATION_SECONDS
  expiration_seconds = max(settings.MIN_EXPIRATION_SECONDS, expiration_seconds)
  if not new_project_name:
    new_project_name = 'Copy of {}'.format(template_project.project_name)
  description = template_project.project_description
  retries = 5
  for i in range(0, retries):
    try:
      project = CreateProject(
        owner=owner,
        template_url=template_project.template_url,
        html_url=template_project.html_url,
        project_name=new_project_name,
        project_description=description,
        show_files=template_project.show_files,
        read_only_files=template_project.read_only_files,
        read_only_demo_url=template_project.read_only_demo_url,
        expiration_seconds=expiration_seconds,
        orderby=template_project.orderby,
        in_progress_task_name='copy_project')
      src_tree = _CreateProjectTree(template_project)
      dst_tree = _CreateProjectTree(project)
      CopyTree(dst_tree, src_tree)
      project.in_progress_task_name=None
      project.put()
      return project
    except Exception, e:
      if i == retries - 1:
        raise
      shared.w('Will retry CreateProject which encountered {}'.format(e))
      time.sleep(random.randint(1, 4))


def CopyTree(dst_tree, src_tree):
  files = src_tree.GetFiles(None)
  dst_tree.PutFiles(files)


def ResetProject(project_id, project_tree):
  project_tree.Clear()
  project = GetProject(project_id)
  repo = GetRepo(project.template_url)
  tp = repo.project.get()
  template_tree = _CreateProjectTree(tp)
  CopyTree(project_tree, template_tree)
  return project


def GetProjectData(project_id, project_tree):
  """Get project data.

  Used to the playground to provide project downloads.

  Args:
    project_id: The project id.
    project_tree: The project tree.
  Returns:
    Project data as a dict.
  """
  project = GetProject(project_id)
  project_name = project.project_name
  paths = project_tree.ListDirectory(None)
  files = []
  for path in paths:
    if os.path.isdir(path):
      continue
    content = project_tree.GetFileContents(path)
    files.append({'path': path, 'content': content})
  return {'project_name': project_name, 'files': files}


def RenameProject(project_id, project_name):
  project = GetProject(project_id)
  project.project_name = project_name
  project.put()
  return project


@ndb.transactional
def UpdateProject(project_id, data):
  project = GetProject(project_id)
  if data:
    project.project_name = data.get('project_name', project.project_name)
    project.project_description = data.get('project_description',
                                           project.project_description)
    project.show_files = data.get('show_files', project.show_files)
    project.read_only_files = data.get('read_only_files',
                                       project.read_only_files)
    project.read_only_demo_url = data.get('read_only_demo_url',
                                          project.read_only_demo_url)
    project.orderby = data.get('orderby', project.orderby)
  project.put()
  return project


def AdoptProjects(dst_user_id, src_user_id):
  """Transfer project ownership to a new user."""

  @ndb.transactional(xg=True)
  def _AdoptProject(project_key, dst_user_key, src_user_key):
    prj, dst_user, src_user = ndb.get_multi([project_key, dst_user_key,
                                             src_user_key])
    if project_key not in src_user.projects:
      # another concurrent request and transaction beat us to it
      return
    src_user.projects.remove(project_key)
    dst_user.projects.append(project_key)
    prj.owner = dst_user_key.id()
    prj.writers.remove(src_user_key.id())
    prj.writers.append(dst_user_key.id())
    ndb.put_multi([prj, dst_user, src_user])

  src_user = GetUser(src_user_id)
  if not src_user or not src_user.projects:
    return
  dst_user = GetOrCreateUser(dst_user_id)
  for project_key in src_user.projects:
    # slow, but transactionable
    _AdoptProject(project_key, dst_user.key, src_user.key)


def GetGlobalRootEntity():
  return Global.get_or_insert('config', namespace=settings.PLAYGROUND_NAMESPACE)


def GetPublicTemplateOwner():
  return GetOrCreateUser(settings.PUBLIC_PROJECT_TEMPLATE_OWNER)


def GetManualTemplateOwner():
  return GetOrCreateUser(settings.MANUAL_PROJECT_TEMPLATE_OWNER)


def GetRepoCollection(url):
  return RepoCollection.get_by_id(url, parent=GetGlobalRootEntity().key)


def DeleteReposAndTemplateProjects():
  """Delete repos and related template projects."""
  user = GetPublicTemplateOwner()

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


@ndb.transactional(xg=True)
def CreateProject(owner, template_url, html_url, project_name,
                  project_description, show_files, read_only_files,
                  read_only_demo_url, expiration_seconds, orderby=None,
                  in_progress_task_name=None):
  """Create a new user project.

  Args:
    owner: The user for which the project is to be created.
    template_url: The template URL to populate the project files or None.
    html_url: The end user URL to populate the project files or None.
    project_name: The project name.
    project_description: The project description.
    show_files: List of files to open.
    read_only_files: List of files that should be shown in read-only mode.
    read_only_demo_url: URL to use for the "run" frame if the sample is
        read-only, or None to run the sample code with mimic in the usual way.
    expiration_seconds: Seconds till expiration, from last update.
    orderby: String used for project descending sort order. Optional.
    in_progress_task_name: Owning task name. Optional.

  Returns:
    The new project entity.

  Raises:
    PlaygroundError: If the project name already exists.
  """
  prj = Project(project_name=project_name,
                project_description=project_description,
                owner=owner.key.id(),
                writers=[owner.key.id()],
                template_url=template_url,
                html_url=html_url,
                show_files=show_files,
                read_only_files=read_only_files,
                read_only_demo_url=read_only_demo_url,
                orderby=orderby,
                in_progress_task_name=in_progress_task_name,
                access_key=secret.GenerateRandomString(),
                namespace=settings.PLAYGROUND_NAMESPACE,
                expiration_seconds=expiration_seconds)
  prj.put()
  # transactional get before update
  owner = owner.key.get()
  owner.projects.append(prj.key)
  owner.put()
  # call taskqueue to schedule expiration
  if expiration_seconds:
    expiration_date = prj.updated + datetime.timedelta(0, expiration_seconds)
    # explicit expiration_date avoids reading back all the files we just created
    ScheduleExpiration(prj, expiration_date)
  return prj


def GetProjectLastModified(project):
  """Gets the time that the project was last modified.

  Args:
    project: the playground project
  Returns:
    A datetime object.
  """
  last_modified = project.updated
  tree = _CreateProjectTree(project)
  paths = tree.ListDirectory(None)
  for path in paths:
    if path.endswith('/'):
      continue
    file_mtime = tree.GetFileLastModified(path)
    if file_mtime > last_modified:
      last_modified = file_mtime
  return last_modified


def ScheduleExpiration(project, expiration_date):
  base_url = '/playground/p/{0}/check_expiration'
  expiration_url = base_url.format(project.key.id())
  if expiration_date is None:
    # deteimne expiration date based on last file access
    expiration_date = (GetProjectLastModified(project) +
                       datetime.timedelta(0, project.expiration_seconds))
  taskqueue.add(queue_name='expiration',
                url=expiration_url,
                eta=expiration_date)


def CheckExpiration(project):
  """Expires the project if appropriate.

  Project expires if more than expiration_seconds
  seconds has elapsed since last modification.  Used
  in the CheckExpiration request handler.

  Args:
    project: the playground project
  """
  expiration_seconds = project.expiration_seconds
  now = datetime.datetime.now()
  current_expiration_date = (GetProjectLastModified(project) +
                             datetime.timedelta(0, expiration_seconds))
  # Expire the project
  if now > current_expiration_date:
    DeleteProject(project)
  # Defer expiration
  else:
    ScheduleExpiration(project, None)


@ndb.transactional()
def SetProjectOwningTask(project_key, in_progress_task_name):
  project = project_key.get()
  if (None not in (in_progress_task_name, project.in_progress_task_name)
      and in_progress_task_name != project.in_progress_task_name):
    shared.e('illegal project task move {} -> {}'
             .format(project.in_progress_task_name, in_progress_task_name))
  project.in_progress_task_name = in_progress_task_name
  project.put()
  return project


def GetOrInsertRepoCollection(uri, description):
  return RepoCollection.get_or_insert(uri, description=description,
                                      parent=GetGlobalRootEntity().key)


def DeleteProject(project):
  """Delete an existing project."""
  assert project
  tree = _CreateProjectTree(project)
  # 1. delete files
  tree.Clear()

  @ndb.transactional(xg=True)
  def DelProject():
    # 2. get current entities
    prj = project.key.get()
    user_key = ndb.Key(User, prj.owner, namespace=settings.PLAYGROUND_NAMESPACE)
    usr = user_key.get()
    # 3. delete project
    prj.key.delete()
    # 4. delete project references
    if prj.key in usr.projects:
      usr.projects.remove(prj.key)
      usr.put()
    else:
      shared.i('ignoring project key {} not found in user projects {}'
               .format(prj.key, usr.projects))

  @ndb.transactional(xg=True)
  def DelReposAndProject(keys):
    ndb.delete_multi(keys)
    DelProject()

  repo_query = Repo.query(namespace=settings.PLAYGROUND_NAMESPACE)
  repo_query = repo_query.filter(Repo.project == project.key)
  keys = repo_query.fetch(keys_only=True)
  if keys:
    DelReposAndProject(keys)
  else:
    DelProject()
