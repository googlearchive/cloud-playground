"""Class to maintain application secrets in the datastore."""

from webapp2_extras import security

import settings

from google.appengine.ext import ndb


class _AhBlissSecret(ndb.Model):
  """A model which stores secret keys."""
  secret_key = ndb.StringProperty(indexed=False)
  created = ndb.DateTimeProperty(auto_now_add=True, indexed=False)
  udpated = ndb.DateTimeProperty(auto_now=True, indexed=False)


def GetSecret(key_name, entropy):
  """Returns and lazily creates random application secrets."""
  # optimistically try fast, transactionless get_by_key_name
  entity = _AhBlissSecret.get_by_id(key_name, namespace=settings.BLISS_NAMESPACE)
  # fall back to slower get_or_insert
  if not entity:
    candidate_secret_key = security.generate_random_string(
        entropy=entropy, pool=security.LOWERCASE_ALPHANUMERIC)
    entity = _AhBlissSecret.get_or_insert(key_name,
                                       secret_key=candidate_secret_key,
                                       namespace=settings.BLISS_NAMESPACE)
  # return the one true secret key from the datastore
  return str(entity.secret_key)
