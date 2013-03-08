"""Module containing template WSGI handlers."""

import webapp2

import codesite
import github
import model
import settings
import shared


class PopulateTemplateSource(webapp2.RequestHandler):

  def post(self):
    key = self.request.get('key')
    template_source = model.GetTemplateSource(key)
    url = template_source.key.id()
    if url == settings.TEMPLATE_PROJECT_DIR:
      return model.PopulateFileSystemTemplates(template_source)
    elif codesite.IsCodesiteURL(url):
      return codesite.PopulateTemplates(template_source)
    elif github.IsGithubURL(url):
      return github.PopulateTemplates(template_source)
    else:
      shared.e('Unknown URL template %s' % url)


app = webapp2.WSGIApplication([
    # templates
    ('/_playground_tasks/template_source/populate', PopulateTemplateSource),
], debug=True)
