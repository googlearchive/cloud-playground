"""Module containing template WSGI handlers."""

import webapp2

import model

from template import templates


class PopulateTemplateSource(webapp2.RequestHandler):

  def post(self):
    key = self.request.get('key')
    template_source = model.GetTemplateSource(key)
    url = template_source.key.id()
    collection = templates.GetCollection(url)
    collection.PopulateTemplates()
    templates.ClearCache()


app = webapp2.WSGIApplication([
    # templates
    ('/_playground_tasks/template_source/populate', PopulateTemplateSource),
], debug=True)
