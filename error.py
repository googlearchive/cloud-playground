"""Exceptions raised in playground app."""


class PlaygroundError(Exception):

  def __init__(self, message):
    super(PlaygroundError, self).__init__(message)
