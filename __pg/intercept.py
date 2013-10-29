"""Module containing the mimic WSGI intercept apps."""

from mimic import mimic_wsgi

from . import middleware
from . import settings
from . import wsgi_config


control_app = mimic_wsgi.Mimic
control_app = middleware.MimicControlAccessFilter(control_app)
control_app = middleware.Session(control_app, wsgi_config.WSGI_CONFIG)
control_app = middleware.AccessKeyHttpHeaderFilter(control_app)
control_app = middleware.Redirector(control_app)
control_app = middleware.ProjectFilter(control_app)
control_app = middleware.ErrorHandler(control_app, debug=settings.DEBUG)

user_app = mimic_wsgi.Mimic
user_app = middleware.MimicControlAccessFilter(user_app)
user_app = middleware.AccessKeyCookieFilter(user_app)
user_app = middleware.AccessKeyHttpHeaderFilter(user_app)
user_app = middleware.Redirector(user_app)
user_app = middleware.ProjectFilter(user_app)
user_app = middleware.ErrorHandler(user_app, debug=settings.DEBUG)
