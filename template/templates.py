"""Module for dealing with project templates."""

from google.appengine.api import memcache
from google.appengine.api import taskqueue
from google.appengine.ext import ndb

import model
import settings
import shared

from . import codesite
from . import filesystem
from . import github


# tuples containing templates (uri, description)
REPO_COLLECTIONS = [
    (settings.TEMPLATE_PROJECT_DIR,
     'Playground Templates'),
    ('https://google-app-engine-samples.googlecode.com/svn/trunk/',
     'Python App Engine Samples'),
    ('https://google-app-engine-samples.googlecode.com/svn/trunk/python27/',
     'Python 2.7 App Engine Samples'),
    ('https://api.github.com/users/GoogleCloudPlatform/repos',
     'Google Cloud Platform samples on github'),
]

_MEMCACHE_KEY_REPO_COLLECTIONS = '{0}'.format(model.RepoCollection.__name__)

_MEMCACHE_KEY_TEMPLATES = '{0}'.format(model.Template.__name__)


def ClearCache():
  # TODO: determine why the just deleting our keys is insufficient:
  # memcache.delete_multi(keys=[_MEMCACHE_KEY_REPO_COLLECTIONS,
  #                       _MEMCACHE_KEY_TEMPLATES])
  memcache.flush_all()


def GetRepoCollections():
  """Get repo collections."""
  sources = memcache.get(_MEMCACHE_KEY_REPO_COLLECTIONS,
                         namespace=settings.PLAYGROUND_NAMESPACE)
  if sources:
    return sources
  query = model.RepoCollection.query(ancestor=model.GetGlobalRootEntity().key)
  sources = query.fetch()
  if not sources:
    sources = _GetRepoCollections()
  sources.sort(key=lambda source: source.description)
  memcache.set(_MEMCACHE_KEY_REPO_COLLECTIONS,
               sources,
               namespace=settings.PLAYGROUND_NAMESPACE,
               time=shared.MEMCACHE_TIME)
  return sources


def GetTemplates():
  """Get templates from a given repo collection."""
  templates = memcache.get(_MEMCACHE_KEY_TEMPLATES,
                           namespace=settings.PLAYGROUND_NAMESPACE)
  if templates:
    return templates
  templates = (model.Template.query(namespace=settings.PLAYGROUND_NAMESPACE)
               .order(model.Template.key).fetch())
  templates.sort(key=lambda template: template.name.lower())
  memcache.set(_MEMCACHE_KEY_TEMPLATES,
               templates,
               namespace=settings.PLAYGROUND_NAMESPACE,
               time=shared.MEMCACHE_TIME)
  return templates


@ndb.transactional(xg=True)
def _GetRepoCollections():
  sources = []
  for uri, description in REPO_COLLECTIONS:
    key = ndb.Key(model.RepoCollection,
                  uri,
                  parent=model.GetGlobalRootEntity().key)
    source = key.get()
    # avoid race condition when multiple requests call into this method
    if source:
      continue
    source = model.RepoCollection(key=key, description=description)
    shared.w('adding task to populate repo collection {0!r}'.format(uri))
    taskqueue.add(url='/_playground_tasks/populate_repo_collection',
                  params={'repo_collection_url': source.key.id()})
    sources.append(source)
  ndb.put_multi(sources)
  return sources


def GetCollection(repo_collection_url):
  repo_collection = model.GetRepoCollection(repo_collection_url)
  if filesystem.IsValidUrl(repo_collection_url):
    return filesystem.FilesystemTemplateCollection(repo_collection)
  elif codesite.IsValidUrl(repo_collection_url):
    return codesite.CodesiteTemplateCollection(repo_collection)
  elif github.IsValidUrl(repo_collection_url):
    return github.GithubTemplateCollection(repo_collection)
  else:
    raise ValueError('Unknown repo collection URL {0}'
                     .format(repo_collection_url))


def PopulateProjectFromTemplateUrl(tree, template_url):
  """Populate project from a template URL.

  Args:
    tree: A tree object to use to retrieve files.
    template_url: The template URL to populate the project files.
  """
  collection = GetCollection(template_url)
  collection.PopulateProjectFromTemplateUrl(tree, template_url)
