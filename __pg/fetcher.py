"""Module for url fetching functions."""

import httplib
import json

from . import model
from . import shared

from google.appengine.api import urlfetch


# pylint:disable-msg=nonstandard-exception
class FetchError(urlfetch.Error):
  """URL Fetch error for response code != 200."""

  def __init__(self, url, response):
    self.url = url
    self.response = response

  def __str__(self):
    return 'Status code {0} fetching {1} {2}'.format(self.response.status_code,
                                                     self.url,
                                                     self.response.content)


class Fetcher(object):
  """A wrapper for URL fetch which performs validation and conversion."""

  def __init__(self, url, url_auth_suffix='', follow_redirects=False,
               headers=None):
    if headers is None:
      headers = {}
    self.url = url
    self.response = None
    self.etag, self.response_content = model.GetResource(url)
    if self.etag:
      headers['If-None-Match'] = '{}'.format(self.etag)
    self.rpc = urlfetch.create_rpc()
    full_url = '{}{}'.format(url, url_auth_suffix)
    # shared.i('urlfetch.make_fetch_call {} {}'.format(headers, full_url))
    urlfetch.make_fetch_call(self.rpc, full_url, headers=headers,
                             follow_redirects=follow_redirects,
                             validate_certificate=True)

  def _CheckResponse(self):
    """Verify the current response."""
    if self.response:
      return
    self.response = self.rpc.get_result()
    shared.i('{} {}'.format(self.response.status_code, self.url))
    if self.response.content_was_truncated:
      raise FetchError(self.url, self.response)
    if self.response.status_code == httplib.NOT_MODIFIED:
      return
    if self.response.status_code == httplib.OK:
      self.response_content = self.response.content
      self.etag = self.response.headers['ETag']
      model.PutResource(self.url, self.etag, self.response_content)
      return
    if self.etag and self.response_content:
      shared.w('using existing content etag={}, url={}'
               .format(self.etag, self.url))
      return
    raise FetchError(self.url, self.response)

  @property
  def content(self):
    self._CheckResponse()
    return self.response_content

  @property
  def json_content(self):
    return json.loads(self.content)
