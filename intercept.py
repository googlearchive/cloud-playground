"""Module containing the mimic WSGI intercept app."""

from mimic import mimic_wsgi

import middleware
import settings
import shared


app = mimic_wsgi.Mimic
app = middleware.MimicControlAccessFilter(app)
app = middleware.Session(app, settings.WSGI_CONFIG)
app = middleware.AccessKeyHttpHeaderFilter(app)
app = middleware.Redirector(app)
app = middleware.ProjectFilter(app)
app = middleware.ErrorHandler(app, debug=settings.DEBUG)

user_app = mimic_wsgi.Mimic
user_app = middleware.MimicControlAccessFilter(user_app)
user_app = middleware.AccessKeyCookieFilter(user_app)
user_app = middleware.AccessKeyHttpHeaderFilter(user_app)
user_app = middleware.Redirector(user_app)
user_app = middleware.ProjectFilter(user_app)
user_app = middleware.ErrorHandler(user_app, debug=settings.DEBUG)
