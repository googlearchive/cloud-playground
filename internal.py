"""Module containing the internal WSGI handlers."""

import webapp2

from template import templates

import middleware
import settings


class Warmup(webapp2.RequestHandler):
  """Handler for warmup/start requests"""

  def get(self):
    templates.GetRepoCollections()


app = webapp2.WSGIApplication([
    # warmup requests
    ('/_ah/warmup', Warmup),

    # backends in the dev_appserver
    ('/_ah/start', Warmup),
], debug=settings.DEBUG)
app = middleware.ProjectFilter(app)
