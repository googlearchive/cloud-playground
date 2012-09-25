import httplib
import logging
import model
import os
import re
import shared
import sys
import traceback

from google.appengine.api import memcache
from google.appengine.api import urlfetch


_CODESITE_RE = re.compile('^https?://[^/]+.googlecode.com/.+$')

_CODESITE_DIR_FOOTER = """<em><a href="http://code.google.com/">Google Code</a> powered by """
_CODESITE_DIR_PATH_RE = re.compile('<li><a href="([^"/]+/?)">[^<]+</a></li>')


def fetch(url, async=False):
  rpc = urlfetch.create_rpc()
  urlfetch.make_fetch_call(rpc, url,
                           follow_redirects=True,
                           validate_certificate=True)
  if async:
    return rpc
  response = rpc.get_result()
  if response.status_code != httplib.OK:
    shared.e('Status code {0} fetching {1}]\n{2}', response.status_code, url,
             response.content)
  return response


def IsCodesiteURL(url):
  return _CODESITE_RE.match(url)


def _GetChildPaths(page):
  if _CODESITE_DIR_FOOTER not in page:
    return []
  paths = _CODESITE_DIR_PATH_RE.findall(page)
  paths = [d for d in paths if not d.startswith('.')]
  return paths

def _GetTemplates(template_source):
  baseurl = template_source.key.id()
  page = fetch(baseurl).content
  candidates = _GetChildPaths(page)
  rpcs = []

  # we found a project in the root directory
  if 'app.yaml' in candidates:
    candidates.insert(0, '')

  if shared.IsDevAppserver():
    # fetch fewer templates during development
    candidates = candidates[:3]

  for c in candidates:
    if c and not c.endswith('/'):
      continue
    project_url = '{0}{1}'.format(baseurl, c)
    app_yaml_url = '{0}app.yaml'.format(project_url)
    rpc = fetch(app_yaml_url, async=True)
    rpcs.append((c, project_url, app_yaml_url, rpc))

  samples = []
  for c, project_url, app_yaml_url, rpc in rpcs:
    try:
      result = rpc.get_result()
      shared.w('{0} {1}'.format(result.status_code, app_yaml_url))
      if result.status_code != 200:
        continue
      s = model._AhTemplate(parent=template_source.key,
                            id=project_url,
                            name=c or project_url,
                            description=project_url)
      samples.append(s)
    except:
      exc_info = sys.exc_info()
      formatted_exception = traceback.format_exception(exc_info[0], exc_info[1],
                                                       exc_info[2])
      shared.w('Skipping %s' % project_url)
      for line in [line for line in formatted_exception if line]:
        shared.w(line)
      pass
  model.ndb.put_multi(samples)
  return samples


# TODO: fetch remote files once in a task, not on every project creation
def PopulateProjectFromCodesite(tree, template_url, project_name):
  tree.Clear()

  baseurl = template_url

  def add_files(dirname):
    url = os.path.join(baseurl, dirname)
    page = fetch(url).content
    paths = _GetChildPaths(page)
    shared.w('{0} -> {1}', url, paths)
    if not paths:
      logging.info('- %s' % dirname)
      tree.SetFile(dirname, page)
    for path in paths:
      if shared.GetExtension(path) in shared._SKIP_EXTENSIONS:
        continue
      relpath = os.path.join(dirname, path)
      fullpath = os.path.join(baseurl, dirname, path)
      add_files(relpath)

  add_files('')
