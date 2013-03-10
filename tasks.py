"""Module containing template WSGI handlers."""

import webapp2

import model
import shared

from template import templates


class PopulateRepoCollection(webapp2.RequestHandler):

  def post(self):
    repo_collection_url = self.request.get('repo_collection_url')
    shared.w('Populating repo collection {0}'.format(repo_collection_url))
    collection = templates.GetCollection(repo_collection_url)
    collection.PopulateTemplates()
    templates.ClearCache()


app = webapp2.WSGIApplication([
    ('/_playground_tasks/populate_repo_collection', PopulateRepoCollection),
], debug=True)
