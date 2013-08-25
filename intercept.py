"""Module containing the mimic WSGI intercept app."""

from mimic import mimic_wsgi

import middleware
import settings
import shared


app = mimic_wsgi.Mimic
app = middleware.MimicControlAccessFilter(app)
if shared.ThisIsPlaygroundApp():
  app = middleware.Session(app, settings.WSGI_CONFIG)
else:
  app = middleware.AccessKeyCookieFilter(app)
app = middleware.AccessKeyHttpHeaderFilter(app)
app = middleware.Redirector(app)
app = middleware.ProjectFilter(app)
app = middleware.ErrorHandler(app, debug=settings.DEBUG)
