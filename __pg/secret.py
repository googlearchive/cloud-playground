"""Class to maintain application secrets in the datastore."""

from webapp2_extras import security

from . import settings

from google.appengine.ext import ndb


class Secret(ndb.Model):
  """A model which stores secret keys."""
  secret_key = ndb.StringProperty(indexed=False)
  created = ndb.DateTimeProperty(auto_now_add=True, indexed=False)
  updated = ndb.DateTimeProperty(auto_now=True, indexed=False)


def GenerateRandomString(entropy=128, pool=security.LOWERCASE_ALPHANUMERIC):
  return security.generate_random_string(entropy=entropy, pool=pool)


def GetSecret(key_name, entropy):
  """Returns and lazily creates random application secrets."""
  # optimistically try fast, transactionless get_by_key_name
  entity = Secret.get_by_id(key_name, namespace=settings.PLAYGROUND_NAMESPACE)
  # fall back to slower get_or_insert
  if not entity:
    candidate_secret_key = GenerateRandomString(entropy)
    entity = Secret.get_or_insert(key_name, secret_key=candidate_secret_key,
                                  namespace=settings.PLAYGROUND_NAMESPACE)
  # return the one true secret key from the datastore
  return str(entity.secret_key)
