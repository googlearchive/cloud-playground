"""Exceptions raised in playground app."""

import httplib
import logging
import sys
import traceback

from . import settings
from . import jsonutil


class PlaygroundError(Exception):
  """Playground specific error class."""

  def __init__(self, status_code, message):
    super(PlaygroundError, self).__init__(message)
    self.status_code = status_code

  def __repr__(self):
    text = '{}<{} {}>'.format(self.__class__, self.status_code, self.message)
    return text.encode('unicode-escape')


def Abort(status_code, message):
  logging.debug('Abort {} {}'.format(status_code, message))
  raise PlaygroundError(status_code, message)


def MakeErrorResponse(exception, debug_mode):
  """Generate a HTTP error response.

  Args:
    exception: the underlying cause of the to be created error response.
    debug_mode: whether or not a stack trace should be included in the response.
  Returns:
    HTTP response tuple of consisting of status line, extra headers and
    response body.
  """
  headers = [
      ('content-type', 'text/plain; charset=utf-8'),
      # Note App Engine automatically sets a 'Date' header for us. See
      # https://developers.google.com/appengine/docs/python/runtime#Responses
      ('Expires', settings.LONG_AGO),
      ('Cache-Control', 'private, max-age=0'),
  ]
  if isinstance(exception, PlaygroundError):
    status_code = exception.status_code
    headers.append(
        ('X-Cloud-Playground-Error', 'True')
    )
    message = exception.message
  else:
    logging.exception(exception)
    status_code = 500
    exc_info = sys.exc_info()
    formatted_exception = traceback.format_exception(exc_info[0], exc_info[1],
                                                     exc_info[2])
    if debug_mode:
      message = ('\n{}'.format('\n'.join(formatted_exception)))
    else:
      message = 'Ouch. How awkward.'
  status = '{} {}'.format(status_code, httplib.responses[status_code])
  body = message
  return status, headers, body
