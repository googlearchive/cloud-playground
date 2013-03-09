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
TEMPLATE_SOURCES = [
    (settings.TEMPLATE_PROJECT_DIR,
     'Playground Templates'),
    ('https://google-app-engine-samples.googlecode.com/svn/trunk/',
     'Python App Engine Samples'),
    ('https://google-app-engine-samples.googlecode.com/svn/trunk/python27/',
     'Python 2.7 App Engine Samples'),
    ('https://api.github.com/users/GoogleCloudPlatform/repos',
     'Google Cloud Platform samples on github'),
]

_MEMCACHE_KEY_TEMPLATE_SOURCES = '{0}'.format(model.TemplateSource.__name__)

_MEMCACHE_KEY_TEMPLATES = '{0}'.format(model.Template.__name__)


def ClearCache():
  # TODO: determine why the just deleting our keys is insufficient:
  # memcache.delete_multi(keys=[_MEMCACHE_KEY_TEMPLATE_SOURCES,
  #                       _MEMCACHE_KEY_TEMPLATES])
  memcache.flush_all()


def GetTemplateSources():
  """Get template sources."""
  sources = memcache.get(_MEMCACHE_KEY_TEMPLATE_SOURCES,
                         namespace=settings.PLAYGROUND_NAMESPACE)
  if sources:
    return sources
  query = model.TemplateSource.query(ancestor=model.GetGlobalRootEntity().key)
  sources = query.fetch()
  if not sources:
    sources = _GetTemplateSources()
  sources.sort(key=lambda source: source.description)
  memcache.set(_MEMCACHE_KEY_TEMPLATE_SOURCES,
               sources,
               namespace=settings.PLAYGROUND_NAMESPACE,
               time=shared.MEMCACHE_TIME)
  return sources


def GetTemplates():
  """Get templates from a given template source."""
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
def _GetTemplateSources():
  sources = []
  for uri, description in TEMPLATE_SOURCES:
    key = ndb.Key(model.TemplateSource,
                  uri,
                  parent=model.GetGlobalRootEntity().key)
    source = key.get()
    # avoid race condition when multiple requests call into this method
    if source:
      continue
    source = model.TemplateSource(key=key, description=description)
    shared.w('adding task to populate template source {0!r}'.format(uri))
    taskqueue.add(url='/_playground_tasks/template_source/populate',
                  params={'key': source.key.id()})
    sources.append(source)
  ndb.put_multi(sources)
  return sources


def GetCollection(url):
  template_source = model.GetTemplateSource(url)
  if filesystem.IsValidUrl(url):
    return filesystem.FilesystemTemplateCollection(template_source)
  elif codesite.IsValidUrl(url):
    return codesite.CodesiteTemplateCollection(template_source)
  elif github.IsValidUrl(url):
    return github.GithubTemplateCollection(template_source)
  else:
    raise ValueError('Unknown URL template {0}'.format(url))


def PopulateProjectFromTemplateUrl(tree, template_url):
  """Populate project from a template URL.

  Args:
    tree: A tree object to use to retrieve files.
    template_url: The template URL to populate the project files.
  """
  collection = GetCollection(template_url)
  collection.PopulateProjectFromTemplateUrl(tree, template_url)
