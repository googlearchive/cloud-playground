"""Module containing template WSGI handlers."""

import webapp2

import model


class PopulateTemplateSource(webapp2.RequestHandler):

  def post(self):
    url = self.request.get('key')
    template_source = model.GetTemplateSource(url)
    model._GetTemplates(template_source)
    

app = webapp2.WSGIApplication([
    # templates
    ('/_bliss_tasks/template_source/populate', PopulateTemplateSource),
], debug=True)
