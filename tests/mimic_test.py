#!/usr/bin/env python
#
# Copyright 2012 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Integration tests for mimic.py."""

import cStringIO
from email import feedparser
import httplib
import os
import re
import sys


# Import test_util first, to ensure python27 / webapp2 are setup correctly
from tests import test_util  # pylint: disable-msg=C6203

from __mimic import common  # pylint: disable-msg=C6203
from __mimic import datastore_tree
from __mimic import mimic
import yaml

import unittest


# https://developers.google.com/appengine/docs/python/gettingstarted/helloworld
_SIMPLE_CGI_SCRIPT = """
print 'Status: 200'
print 'Content-Type: text/plain'
print
print 'hello'
"""

# https://developers.google.com/appengine/docs/python/gettingstarted/usingwebapp
_MAIN_CGI_WSGI_SCRIPT = r"""
from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app

class MainPage(webapp.RequestHandler):
    def get(self):
        self.response.headers['Content-Type'] = 'text/plain'
        self.response.out.write('Hello, main cgi wsgi\n')

application = webapp.WSGIApplication(
                                     [('/.*', MainPage)],
                                     debug=True)

def main():
    run_wsgi_app(application)

if __name__ == "__main__":
  main()
"""

_SIMPLE_WEBAPP = r"""
from google.appengine.ext import webapp

class MainPage(webapp.RequestHandler):
  def get(self):
    self.response.headers['Content-Type'] = 'text/plain'
    self.response.out.write('Hello, webapp\n')

app = webapp.WSGIApplication(
                             [('/.*', MainPage)],
                             debug=True)
"""

# https://developers.google.com/appengine/docs/python/gettingstartedpython27/helloworld
_SIMPLE_WEBAPP2 = r"""
from google.appengine.ext import webapp as webapp2
# It's easy to mess up imports and accidentally use the old webapp
assert hasattr(webapp2, 'get_app'), 'Tests must use webapp2'

class MainPage(webapp2.RequestHandler):
  def get(self):
      self.response.headers['Content-Type'] = 'text/plain'
      self.response.out.write('Hello, webapp2\n')

app = webapp2.WSGIApplication([('/.*', MainPage)],
                              debug=True)
"""

_APP_YAML_HEADER = """
application: my-app
version: 1
runtime: python27
api_version: 1
threadsafe: true
"""

_APP_YAML_TEMPLATE = _APP_YAML_HEADER + r"""
%(default_expiration)s

handlers:
- url: /(.*\.py)(\?.*)?
  script: \1
  %(login)s

- url: /(.*\.app)(\?.*)?
  script: \1
  %(login)s

- url: /(default_expiration.txt)
  static_files: static/\1
  upload: static/default_expiration.txt

- url: /(1d2h3m4s.txt)
  static_files: static/\1
  upload: static/1d2h3m4s.txt
  expiration: "1d 2h 3m 4s"

- url: /(.*)
  static_files: static/\1
  upload: static/.*
  %(login)s
  %(expiration)s
"""


def MakeAppYaml(login='', default_expiration='', expiration=''):
  """Construct the text of an app.yaml file with the specified login value."""
  if login:
    login = 'login: {0}'.format(login)
  if default_expiration:
    default_expiration = 'default_expiration: "{0}"'.format(default_expiration)
  if expiration:
    expiration = 'expiration: "{0}"'.format(expiration)
  values = {
      'login': login,
      'default_expiration': default_expiration,
      'expiration': expiration,
  }
  return _APP_YAML_TEMPLATE % values

_GENERIC_APP_YAML = MakeAppYaml()


class FakeUser(object):
  """A fake User object for authentication."""

  def __init__(self, nickname):
    self._nickname = nickname

  def nickname(self):  # pylint: disable-msg=C6409
    return self._nickname


class FakeUsersMod(object):
  """A fake users modules for authentication."""

  def __init__(self):
    self._is_admin = None
    self._is_user = None
    self._current_user = None

  def set_current_user_is_admin(self, admin):  # pylint: disable-msg=C6409
    self._is_admin = admin

  def is_current_user_admin(self):  # pylint: disable-msg=C6409
    return self._is_admin

  def set_current_user(self, user):  # pylint: disable-msg=C6409
    self._current_user = user

  def get_current_user(self):  # pylint: disable-msg=C6409
    return self._current_user

  def create_login_url(self, continue_url):
    return '/_ah/login?continue={0}'.format(continue_url)

  def create_logout_url(self, continue_url):
    return '/_ah/logout?continue={0}'.format(continue_url)


class MimicTest(unittest.TestCase):
  """Test the entire mimic application."""

  def setUp(self):
    test_util.InitAppHostingApi()
    # used by app_identity.get_default_version_hostname()
    os.environ['DEFAULT_VERSION_HOSTNAME'] = 'your-app-id.appspot.com'
    # we set it here to prevent contaimination, may be overridden in tests
    os.environ['SERVER_NAME'] = 'your-app-id.appspot.com'
    # TODO: add tests for app.yaml 'secure: always'
    os.environ['wsgi.url_scheme'] = 'http'
    os.environ['QUERY_STRING'] = ''
    # files that will be part of the tree
    self._files = {}
    # these are filled in from mimic's response during CallMimic()
    self._status = None
    self._headers = {}
    self._body = ''
    self._users_mod = FakeUsersMod()
    os.environ['HTTP_COOKIE'] = 'SID=ghi; SSID=def; HSID=abc;'

  def tearDown(self):
    pass

  def _CreateTree(self, project_name):
    tree = datastore_tree.DatastoreTree(project_name)
    for path, contents in self._files.items():
      tree.SetFile(path, contents)
    return tree

  def _CallMimic(self, path,
                 http_host='project-name.your-app-id.appspot.com',
                 os_environ=None):
    # TODO: at some point we might need to expand the set of environ
    # variables set, support POST, etc.  For now this is enough to test what
    # we want.
    saved_environ = dict(os.environ.items())
    os.environ['PATH_INFO'] = path
    os.environ['REQUEST_METHOD'] = 'GET'
    os.environ['HTTP_HOST'] = http_host
    # for server name, strip off the optional ':port' from the 'host:port' pair
    os.environ['SERVER_NAME'] = http_host.split(':')[0]
    os.environ.update(os_environ)
    output = cStringIO.StringIO()
    saved_out = sys.stdout
    try:
      sys.stdout = output
      mimic.RunMimic(create_tree_func=self._CreateTree,
                     users_mod=self._users_mod)
    finally:
      sys.stdout = saved_out
      # restore os.environ
      os.environ.update(saved_environ)
      remove_keys = set(os.environ.keys()) - set(saved_environ.keys())
      for k in remove_keys:
        del os.environ[k]

    self._ParseResponse(output.getvalue())

  def _AddFile(self, path, contents):
    """Add a file to the tree used by mimic."""
    self._files[path] = contents

  def _ParseResponse(self, response):
    # Modelled after appengine/runtime/nacl/python/cgi.py
    parser = feedparser.FeedParser()
    # Set headersonly as we never want to parse the body as an email message.
    parser._set_headersonly()  # pylint: disable-msg=W0212
    parser.feed(response)
    parsed_response = parser.close()
    if 'Status' in parsed_response:
      self._status = int(parsed_response['Status'].split(' ', 1)[0])
      del parsed_response['Status']
    else:
      self._status = 200
    self._headers = dict(parsed_response.items())
    self._body = parsed_response.get_payload()

  def _CheckResponse(self, status, content_type):
    self.assertEquals(status, self._status)
    self.assertEquals(content_type, self._headers.get('Content-Type'))

  def assertResponseExpiration(self, seconds):
    expected_cache_control = 'public, max-age={0}'.format(seconds)
    self.assertEquals(expected_cache_control,
                      self._headers.get('Cache-Control'))

  def testNoAppYaml(self):
    self._CallMimic('/')
    self.assertEquals(httplib.NOT_FOUND, self._status)
    self.assertTrue('no app.yaml file' in self._body)

  def testEmptyAppYaml(self):
    self._AddFile('app.yaml', '')
    self._CallMimic('/')
    self.assertEquals(httplib.NOT_FOUND, self._status)
    self.assertTrue('app.yaml configuration is missing or invalid'
                    in self._body)

  def testStaticPage(self):
    self._AddFile('app.yaml', _GENERIC_APP_YAML)
    self._AddFile('static/foo.txt', '123')
    self._CallMimic('/foo.txt')
    self._CheckResponse(httplib.OK, 'text/plain')
    self.assertEquals('123', self._body)

  def testStaticPageNotFound(self):
    self._AddFile('app.yaml', _GENERIC_APP_YAML)
    self._CallMimic('/bar.html')
    self.assertEquals(httplib.NOT_FOUND, self._status)

  def testStaticPageGuessedType(self):
    self._AddFile('app.yaml', _GENERIC_APP_YAML)
    self._AddFile('static/foo.html', '<html>hello</html>')
    self._CallMimic('/foo.html')
    self._CheckResponse(httplib.OK, 'text/html')
    self.assertEquals('<html>hello</html>', self._body)

  def testAppYamlImplicitDefaultExpirationIsTenMinutes(self):
    self._AddFile('app.yaml', MakeAppYaml())
    self._AddFile('static/foo.txt', '123')
    self._CallMimic('/foo.txt')
    self._CheckResponse(httplib.OK, 'text/plain')
    self.assertEquals('123', self._body)
    self.assertResponseExpiration(600)  # 10 minutes

  def testAppYamlExplicitExpiration(self):
    self._AddFile('app.yaml', MakeAppYaml(expiration='2h'))
    self._AddFile('static/foo.txt', '123')
    self._CallMimic('/foo.txt')
    self._CheckResponse(httplib.OK, 'text/plain')
    self.assertEquals('123', self._body)
    self.assertResponseExpiration(7200)  # 2 hours

  def testAppYamlExplicitDefaultExpiration(self):
    self._AddFile('app.yaml', MakeAppYaml(default_expiration='42s'))
    self._AddFile('static/foo.txt', '123')
    self._CallMimic('/foo.txt')
    self._CheckResponse(httplib.OK, 'text/plain')
    self.assertEquals('123', self._body)
    self.assertResponseExpiration(42)  # 42 seconds

  def testAppYamlExpirationOverridesExplicitDefaultExpriation(self):
    self._AddFile('app.yaml', MakeAppYaml(default_expiration='42s'))
    self._AddFile('static/1d2h3m4s.txt', '123')
    self._CallMimic('/1d2h3m4s.txt')
    self._CheckResponse(httplib.OK, 'text/plain')
    self.assertEquals('123', self._body)
    # 60 * 60 * 24 (1d) + 2 * 60 * 60 (2h) + 3 * 60 (3m) + 4 (4s)
    self.assertResponseExpiration(93784)

  def testStaticPageLoginRequired(self):
    self._users_mod.set_current_user(FakeUser('Bob'))
    self._AddFile('app.yaml', MakeAppYaml(login='required'))
    self._AddFile('static/foo.txt', '123')
    self._CallMimic('/foo.txt')
    self._CheckResponse(httplib.OK, 'text/plain')
    self.assertEquals('123', self._body)

  def testStaticPageLoginRequiredForbidden(self):
    self._AddFile('app.yaml', MakeAppYaml(login='required'))
    self._AddFile('static/foo.txt', '123')
    self._CallMimic('/foo.txt')
    self._CheckResponse(httplib.FORBIDDEN, 'text/html')

  def testStaticPageLoginAdmin(self):
    self._users_mod.set_current_user_is_admin(True)
    self._users_mod.set_current_user(FakeUser('Bob'))
    self._AddFile('app.yaml', MakeAppYaml(login='admin'))
    self._AddFile('static/foo.txt', '123')
    self._CallMimic('/foo.txt')
    self._CheckResponse(httplib.OK, 'text/plain')
    self.assertEquals('123', self._body)

  def testStaticPageLoginAdminForbidden(self):
    self._users_mod.set_current_user_is_admin(False)
    self._users_mod.set_current_user(FakeUser('Bob'))
    self._AddFile('app.yaml', MakeAppYaml(login='admin'))
    self._CallMimic('/static/foo.txt')
    self._CheckResponse(httplib.FORBIDDEN, 'text/html')

  def testWebappPage(self):
    self._AddFile('app.yaml', _GENERIC_APP_YAML)
    self._AddFile('webapp.py', _SIMPLE_WEBAPP)
    self._CallMimic('/webapp.app')
    self._CheckResponse(httplib.OK, 'text/plain')
    self.assertEquals('Hello, webapp\n', self._body)

  def testWebapp2Page(self):
    self._AddFile('app.yaml', _GENERIC_APP_YAML)
    self._AddFile('webapp2.py', _SIMPLE_WEBAPP2)
    self._CallMimic('/webapp2.app')
    self._CheckResponse(httplib.OK, 'text/plain')
    self.assertEquals('Hello, webapp2\n', self._body)

  def testMainCgiWsgiScript(self):
    self._AddFile('app.yaml', _GENERIC_APP_YAML)
    self._AddFile('main_cgi_wsgi.py', _MAIN_CGI_WSGI_SCRIPT)
    self._CallMimic('/main_cgi_wsgi.py')
    self._CheckResponse(httplib.OK, 'text/plain')
    self.assertEquals('Hello, main cgi wsgi\n', self._body)

  def testNoDefaultContentType(self):
    self._AddFile('app.yaml', _GENERIC_APP_YAML)
    # Script which does not print any HTTP repsonse headers.
    self._AddFile('main.py', r'print "hello"')
    self._CallMimic('/main.py')
    # Mimic should not add a default Content-Type header.
    self._CheckResponse(httplib.OK, None)
    self.assertEquals('hello\n', self._body)

  def testCgiPage(self):
    self._AddFile('app.yaml', _GENERIC_APP_YAML)
    self._AddFile('main.py', _SIMPLE_CGI_SCRIPT)
    self._CallMimic('/main.py')
    self._CheckResponse(httplib.OK, 'text/plain')
    self.assertEquals('hello\n', self._body)

  def testCgiPageNotFound(self):
    self._AddFile('app.yaml', _GENERIC_APP_YAML)
    self._CallMimic('/main.py')
    self.assertEquals(httplib.NOT_FOUND, self._status)

  def testScritPageLoginRequired(self):
    self._users_mod.set_current_user(FakeUser('Bob'))
    self._AddFile('app.yaml', MakeAppYaml(login='required'))
    self._AddFile('main.py', _SIMPLE_CGI_SCRIPT)
    self._CallMimic('/main.py')
    self._CheckResponse(httplib.OK, 'text/plain')
    self.assertEquals('hello\n', self._body)

  def testScritPageLoginRequiredForbidden(self):
    self._AddFile('app.yaml', MakeAppYaml(login='required'))
    self._AddFile('main.py', _SIMPLE_CGI_SCRIPT)
    self._CallMimic('/main.py')
    self._CheckResponse(httplib.FORBIDDEN, 'text/html')

  def testCgiPageLoginAdmin(self):
    self._users_mod.set_current_user_is_admin(True)
    self._users_mod.set_current_user(FakeUser('Bob'))
    self._AddFile('app.yaml', MakeAppYaml(login='admin'))
    self._AddFile('main.py', _SIMPLE_CGI_SCRIPT)
    self._CallMimic('/main.py')
    self._CheckResponse(httplib.OK, 'text/plain')
    self.assertEquals('hello\n', self._body)

  def testCgiPageLoginAdminForbidden(self):
    self._users_mod.set_current_user_is_admin(False)
    self._users_mod.set_current_user(FakeUser('Bob'))
    self._AddFile('app.yaml', MakeAppYaml(login='admin'))
    self._CallMimic('/main.py')
    self._CheckResponse(httplib.FORBIDDEN, 'text/html')

  def testCgiPageLoginAdminAccessFromCron(self):
    self._users_mod.set_current_user_is_admin(False)
    self._AddFile('app.yaml', MakeAppYaml(login='admin'))
    self._AddFile('main.py', _SIMPLE_CGI_SCRIPT)
    self._CallMimic('/main.py',
                    os_environ={mimic._HTTP_X_APPENGINE_CRON: 'true'})
    self._CheckResponse(httplib.OK, 'text/plain')
    self.assertEquals('hello\n', self._body)

  def testCgiPageLoginAdminAccessFromTaskQueue(self):
    self._users_mod.set_current_user_is_admin(False)
    self._AddFile('app.yaml', MakeAppYaml(login='admin'))
    self._AddFile('main.py', _SIMPLE_CGI_SCRIPT)
    self._CallMimic('/main.py',
                    os_environ={mimic._HTTP_X_APPENGINE_QUEUENAME: 'default'})
    self._CheckResponse(httplib.OK, 'text/plain')
    self.assertEquals('hello\n', self._body)

  def checkHostParseFailure(self, server_name):
    os.environ['SERVER_NAME'] = server_name
    project_name = mimic.GetProjectName()
    self.assertEquals('', project_name)

  def testGetProjectNameAppspot(self):
    os.environ['SERVER_NAME'] = 'project-name.your-app-id.appspot.com'
    project_name = mimic.GetProjectName()
    self.assertEquals('project-name', project_name)

    # Must have project name subdomain
    self.checkHostParseFailure('your-app-id.appspot.com')

  def testGetProjectNameAppspotDashDotDash(self):
    os.environ['SERVER_NAME'] = 'project-name-dot-your-app-id.appspot.com'
    project_name = mimic.GetProjectName()
    self.assertEquals('project-name', project_name)

  def testGetProjectNameCustomDomain(self):
    os.environ['SERVER_NAME'] = 'www.mydomain.com'
    project_name = mimic.GetProjectName()
    self.assertEquals('www', project_name)

    os.environ['SERVER_NAME'] = 'proj1.www.mydomain.com'
    project_name = mimic.GetProjectName()
    self.assertEquals('proj1', project_name)

  def testGetProjectNameLocalhost(self):
    os.environ['HTTP_HOST'] = 'localhost:8080'
    os.environ['SERVER_NAME'] = 'localhost'
    project_name = mimic.GetProjectName()
    self.assertEquals('', project_name)

  def testGetProjectNameCustomDomainDashDotDash(self):
    os.environ['SERVER_NAME'] = 'proj2-dot-www.mydomain.com'
    project_name = mimic.GetProjectName()
    self.assertEquals('proj2', project_name)

  def testVersionIdWithoutProjectName(self):
    self._CallMimic('/_ah/mimic/version_id',
                    http_host='your-app-id.appspot.com')
    self.assertEquals(httplib.OK, self._status)
    # should be a response containing a mimic identifier and some version info
    self.assertTrue(str(common.VERSION_ID) in self._body)

  def testTreeWithoutProjectName(self):
    self._AddFile('app.yaml', _GENERIC_APP_YAML)
    self._AddFile('main.py', _SIMPLE_CGI_SCRIPT)
    # tree should still work even though we've not specified a project name
    self._CallMimic('/main.py', http_host='your-app-id.appspot.com')
    self.assertEquals(httplib.OK, self._status)
    self.assertEquals('hello\n', self._body)

  def SetupDBNamespacing(self):
    person_script = """
from google.appengine.ext import db


class Person(db.Model):
  name = db.StringProperty()
"""

    put_script = """
import person
import os
name = os.environ['PATH_INFO'].split('?')[1]

p = person.Person(key_name='person', name=name)
p.put()
# ensure datastore commit is applied
# See https://developers.google.com/appengine/articles/transaction_isolation
person.Person.get_by_key_name('person')

print 'Content-type: text/plain'
print 'Status: 200'
print ''
print 'name: ' + name
"""

    get_script = """
import person

print 'Content-type: text/plain'
print 'Status: 200'
print ''
p = person.Person.get_by_key_name('person')
if p:
  print 'name: %s, namespace: "%s"' % (p.name, p.key().namespace())
else:
  print 'None'
"""

    query_script = """
from google.appengine.ext import db
import person

print 'Content-type: text/plain'
print 'Status: 200'
print ''
query = db.Query(person.Person)
people = query.fetch(limit=100)
for p in people:
  print 'name: ' + p.name
"""

    gql_query_script = """
from google.appengine.ext import db

print 'Content-type: text/plain'
print 'Status: 200'
print ''
query = db.GqlQuery('SELECT * FROM Person')
people = query.fetch(100)
for p in people:
  print 'name: ' + p.name
"""

    self._AddFile('person.py', person_script)
    self._AddFile('put.py', put_script)
    self._AddFile('get.py', get_script)
    self._AddFile('query.py', query_script)
    self._AddFile('gqlquery.py', gql_query_script)
    self._AddFile('app.yaml', _GENERIC_APP_YAML)

    # Two different projects put two people with the same key_name ('person')
    self._CallMimic('/put.py?JohnDoe', http_host='proj1.your-app-id.appspot.com')
    # make sure it parsed the query arg correctly
    self.assertEquals('name: JohnDoe\n', self._body)

    self._CallMimic('/put.py?JaneDoe', http_host='proj2.your-app-id.appspot.com')
    # make sure it parsed the query arg correctly
    self.assertEquals('name: JaneDoe\n', self._body)

  def testDBNamespacingDifferentProjects(self):
    """Tests that different projects and workspaces see different datastores."""
    self.SetupDBNamespacing()
    # proj1 should see its person, JohnDoe
    self._CallMimic('/get.py', http_host='proj1.your-app-id.appspot.com')
    # the target_env patches should remove the namespace. the actual entity
    # has a namespace of 'proj1-', same for JaneDoe below
    self.assertEquals('name: JohnDoe, namespace: ""\n', self._body)

    # proj2 should see its person, JaneDoe
    self._CallMimic('/get.py', http_host='proj2.your-app-id.appspot.com')
    self.assertEquals('name: JaneDoe, namespace: ""\n', self._body)

  def testDBNamespacingSameProjectDifferentBranch(self):
    """Tests that different branches of the same project see the same data."""
    self.SetupDBNamespacing()
    self._CallMimic('/get.py', http_host='proj1.your-app-id.appspot.com')
    self.assertEquals('name: JohnDoe, namespace: ""\n', self._body)

  def testDBNamespacingDifferentProjectNoData(self):
    """Tests that different projects don't see other projects' data."""
    self.SetupDBNamespacing()
    # different project should'nt see any data
    self._CallMimic('/get.py', http_host='proj3.your-app-id.appspot.com')
    self.assertEquals('None\n', self._body)

  def testDBNamespacingQuerying(self):
    """Tests that querying still works with the namespacing scheme."""
    self.SetupDBNamespacing()
    # querying should still work, proj1 finds John
    self._CallMimic('/query.py', http_host='proj1.your-app-id.appspot.com')
    self.assertEquals('name: JohnDoe\n', self._body)

    # querying should still work, proj2, finds Jane
    self._CallMimic('/query.py', http_host='proj2.your-app-id.appspot.com')
    self.assertEquals('name: JaneDoe\n', self._body)

    # gql should still work
    self._CallMimic('/gqlquery.py', http_host='proj1.your-app-id.appspot.com')
    self.assertEquals('name: JohnDoe\n', self._body)

  def testMemcacheNamespacing(self):
    """Tests that different projects see different memcaches."""

    put_script = """
from google.appengine.api import memcache
import os
value = os.environ['PATH_INFO'].split('?')[1]
memcache.add(key="my_key", value=value, time=3600)

print 'Content-type: text/plain'
print 'Status: 200'
print ''
print 'value: ' + value
"""

    get_script = """
from google.appengine.api import memcache

value = memcache.get(key="my_key")

print 'Content-type: text/plain'
print 'Status: 200'
print ''
print 'value: ' + value
"""

    self._AddFile('put.py', put_script)
    self._AddFile('get.py', get_script)
    self._AddFile('app.yaml', _GENERIC_APP_YAML)

    # put John and Jane using the same key
    self._CallMimic('/put.py?JohnDoe', http_host='proj1.your-app-id.appspot.com')
    self.assertEquals('value: JohnDoe\n', self._body)
    self._CallMimic('/put.py?JaneDoe', http_host='proj2.your-app-id.appspot.com')
    self.assertEquals('value: JaneDoe\n', self._body)

    self._CallMimic('/get.py', http_host='proj1.your-app-id.appspot.com')
    self.assertEquals('value: JohnDoe\n', self._body)

    self._CallMimic('/get.py', http_host='proj2.your-app-id.appspot.com')
    self.assertEquals('value: JaneDoe\n', self._body)

  def testBadAppYaml(self):
    """Tests that parsing a bad app yaml raises the appropriate error."""
    self._AddFile('app.yaml', '"')
    self._CallMimic('/')
    self.assertEquals(httplib.NOT_FOUND, self._status)
    self.assertTrue('app.yaml configuration is missing or invalid'
                    in self._body)


if __name__ == '__main__':
  unittest.main()
