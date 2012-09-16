#!/usr/bin/env python
#
# Copyright 2012 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Classes to help manage patching the Python environment."""



import __builtin__

# A unique sentinel object to signal that a patch isn't installed
_UNINSTALLED = object()


def NeedsOriginal(func):
  """A decorator that indicates the original patch value should be supplied.

  Args:
    func: A callable that is going to be used in a patch.

  Returns:
    The supplied function, with the needs_original attribute added.

  When @NeedsOriginal is used, the original value of the patched function
  will be inserted as the first argument.  For example, one might patch
  open() as follows:

  @patch.NeedsOriginal
  def CustomOpen(original, filename, mode='r', bufsize=-1):
    ...
  """
  func.needs_original = True  # the actual value of the attribute doesn't matter
  return func


class Patch(object):
  """An abstract base class for Patches."""

  def __init__(self, value):
    """Initialize the patch.

    Args:
      value: A value (typically a callable) to use for the patch.  If this value
          has a needs_original attribute then the original value of the patch
          will be inserted as the first argument when value is invoked.
    """
    self._original = _UNINSTALLED
    if hasattr(value, 'needs_original'):

      def Glue(*args, **kwargs):
        return value(self._original, *args, **kwargs)
      self._value = Glue
    else:
      self._value = value

  @property
  def installed(self):
    """Returns True iff the patch is currently installed."""
    return self._original is not _UNINSTALLED

  def Install(self):
    """Install the patch.

    Subclasses must set self._original to the original value of the patched
    object.
    """
    raise NotImplementedError

  def Remove(self):
    """Remove the patch.

    Subclasses must set self._original to _UNINSTALLED after the patch is
    removed.
    """
    raise NotImplementedError


def _GetBuiltinsDict():
  builtins = __builtins__
  if isinstance(builtins, dict):
    return builtins
  else:
    # assume it is a module, get the __dict__
    return builtins.__dict__


class BuiltinPatch(Patch):
  """An object that manages the process of patching a builtin function."""

  # The relationship between __builtins__ and the __builtin__ module has three
  # cases:
  #
  # 1) __builtins__ is __builtin__.  This is the default situation for a python
  #    interpreter, and what we find in production App Engine.
  #
  # 2) __builtins__ is __builtin__.__dict__.  This is true when running google
  #    unit tests.
  #
  # 3) __builtins__ is a custom dictionary.  This is true for dev_appserver.py.
  #
  # __builtins__ is where python looks for functions, so it needs to be patched
  # regardless of which case we're in.  However, in the case #3 it is also
  # necessary to patch the __builtin__ module independently just in case
  # target code uses that module.
  #
  # The one problem is that in case #3 there isn't a single "original"
  # value for the patch - there are in fact two: one from __builtins__ and the
  # other from __builtin__.  If the patched function is invoked via __builtin__
  # then in theory it should call the original __builtin__ (and not the
  # original __builtins__).  Given that invoking via __builtin__ is rare
  # and this case only occurs in dev_appserver.py it isn't worth addressing
  # at this time.

  def __init__(self, name, value):
    """Create a patch.

    Args:
      name: The name of the builtin to patch (e.g. 'open')
      value: The new object to use for the builtin.
    """
    Patch.__init__(self, value)
    self._name = name
    self._saved_builtin = None  # from __builtin__

  def Install(self):
    """Install the patch."""
    assert self._original is _UNINSTALLED
    # save old values
    b_dict = _GetBuiltinsDict()
    self._original = b_dict[self._name]
    self._saved_builtin = getattr(__builtin__, self._name)
    # install new value
    b_dict[self._name] = self._value
    setattr(__builtin__, self._name, self._value)

  def Remove(self):
    """Remove the patch."""
    if self._original is _UNINSTALLED:
      return
    # restore __builtins__
    b_dict = _GetBuiltinsDict()
    b_dict[self._name] = self._original
    self._original = _UNINSTALLED
    # restore __builtin__ (redundant if __builtins__ is __builtin__)
    setattr(__builtin__, self._name, self._saved_builtin)


class AttributePatch(Patch):
  """An object that manages patching an attribute of a parent object.

  The most common use of this is to patch functions within a module, but
  the parent object does not have to be a module.
  """

  def __init__(self, parent, name, value):
    Patch.__init__(self, value)
    self._parent = parent
    self._name = name
    # test borrowed from inspect.classify_class_attrs
    self._is_staticmethod = isinstance(parent.__dict__.get(name), staticmethod)

  def Install(self):
    """Install the patch."""
    assert self._original is _UNINSTALLED
    self._original = getattr(self._parent, self._name)
    if self._is_staticmethod:
      setattr(self._parent, self._name, staticmethod(self._value))
    else:
      setattr(self._parent, self._name, self._value)

  def Remove(self):
    """Remove the patch."""
    if self._original is _UNINSTALLED:
      return
    if self._is_staticmethod:
      setattr(self._parent, self._name, staticmethod(self._original))
    else:
      setattr(self._parent, self._name, self._original)
    self._original = _UNINSTALLED
