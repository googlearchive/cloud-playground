"""Module for url fetching functions."""

import httplib
import json

import model
import shared

from google.appengine.api import urlfetch


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

  def __init__(self, url, url_auth_suffix='', follow_redirects=False, headers={}):
    self.url = url
    self.response = None
    self.response_content = None
    self.resource = model.GetResource(url)
    if self.resource:
      headers['If-None-Match'] = '{}'.format(self.resource.etag)
    self.rpc = urlfetch.create_rpc()
    full_url = '{}{}'.format(url, url_auth_suffix)
    urlfetch.make_fetch_call(self.rpc, full_url, headers=headers,
                             follow_redirects=follow_redirects,
                             validate_certificate=True)

  def _CheckResponse(self):
    if self.response:
      return
    self.response = self.rpc.get_result()
    shared.i('{} {}'.format(self.response.status_code, self.url))
    if self.response.status_code == httplib.NOT_MODIFIED:
      self.response_content = self.resource.content
      return
    if self.response.status_code != httplib.OK:
      raise FetchError(self.url, self.response)
    if self.response.content_was_truncated:
      raise FetchError(self.url, self.response)
    etag = self.response.headers['ETag']
    model.PutResource(self.url, etag, self.response.content)
    self.response_content = self.response.content

  @property
  def content(self):
    self._CheckResponse()
    return self.response_content

  @property
  def json_content(self):
    return json.loads(self.content)
