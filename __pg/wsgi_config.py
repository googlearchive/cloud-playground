from . import secret
from . import settings

WSGI_CONFIG = {
    'webapp2_extras.sessions': {
        'secret_key': secret.GetSecret('webapp2_extras.sessions', entropy=128),
        'cookie_args': settings.SESSION_COOKIE_ARGS,
    }
}

