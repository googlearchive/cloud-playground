"""Exceptions raised in bliss app."""

class BlissError(Exception):

  def __init__(self, message):
    super(BlissError, self).__init__(message)
