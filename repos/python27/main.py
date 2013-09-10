import webapp2


class MainHandler(webapp2.RequestHandler):

  def get(self):  # pylint:disable-msg=invalid-name
    """Handle GET requests."""
    self.response.write("""Hello, world.""")


APP = webapp2.WSGIApplication([
    ('/.*', MainHandler),
], debug=True)

