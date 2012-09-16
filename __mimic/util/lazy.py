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

"""Utility classes and functions for lazy evaluation."""



import functools


class LazyBase(object):
  """An optional base class for classes that wish to use LazyProperty.

  The LazyProperty decorator can be used by any class, but this base class
  provides additional functionality for managing the lazy values dict.  For
  example, a client class may wish to clear any computed lazy values when
  the object is mutated.
  """

  def __init__(self):
    self.__lazy_values = {}

  def ClearLazyValues(self):
    """Clear all cached lazy values.

    The next access to each lazy properties will cause its underlying function
    to be invoked.
    """
    self.__lazy_values.clear()


def LazyProperty(func):
  """A decorator for lazily calculated properties.

  This decorator implicitly creates a read-only property with added logic
  to cache the result.  It can be used in conjuction with the LazyBase
  base class, or completely on its own.

  Typical use:

  class Foo(obect):

    @lazy.LazyProperty
    def bar(self):
      ...

  f = Foo()
  f.bar  # will return result of f.bar()
  f.bar  # will return previous result without calling bar() again

  Args:
    func: A function that computes the value of the property.

  Returns:
    A property object.
  """

  def _LazyFunc(self):
    name = func.__name__
    try:
      return self._LazyBase__lazy_values[name]  # pylint: disable-msg=W0212
    except AttributeError:
      # auto-populate this attribute so that no __init__ code is required
      self._LazyBase__lazy_values = {}
    except KeyError:
      # property hasn't been evaluated yet, fall through
      pass
    # call the underlying function to compute the value
    value = func(self)
    self._LazyBase__lazy_values[name] = value  # pylint: disable-msg=W0212
    return value

  functools.update_wrapper(_LazyFunc, func)
  return property(_LazyFunc)
