"""Module containing template WSGI handlers."""

import webapp2

from . import model
from . import shared

from template import templates


class PopulateRepoCollection(webapp2.RequestHandler):

  def post(self):  # pylint:disable-msg=invalid-name
    repo_collection_url = self.request.get('repo_collection_url')
    shared.i('task {} populating repo collection {}'
             .format(shared.GetCurrentTaskName(), repo_collection_url))
    collection = templates.GetCollection(repo_collection_url)
    if not collection:
      shared.e('missing repo collection {}'.format(repo_collection_url))
    collection.PopulateRepos()
    templates.ClearCache()


class PopulateRepo(webapp2.RequestHandler):

  def post(self):  # pylint:disable-msg=invalid-name
    repo_url = self.request.get('repo_url')
    shared.i('task {} populating repo {}'.format(shared.GetCurrentTaskName(),
                                                 repo_url))
    repo = model.GetRepo(repo_url)
    collection = templates.GetCollection(repo_url)
    if not collection:
      project = repo.project.get()
      model.DeleteProject(project)
      return
    collection.CreateTemplateProject(repo)


app = webapp2.WSGIApplication([
    ('/_playground_tasks/populate_repo_collection', PopulateRepoCollection),
    ('/_playground_tasks/populate_repo', PopulateRepo),
], debug=True)
