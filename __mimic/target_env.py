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

"""Class for establishing a target script execution environment.

TargetEnv requires customized module loading and achieves this via
manipulation of sys.path_hooks and sys.path (see PEP 302 for details).
"""



import errno
import imp
import linecache
import logging
import os
import re
import stat
import string
import StringIO
import sys
import traceback

from __mimic import common
from __mimic import composite_query
from __mimic import target_info
from __mimic.util import patch

from google.appengine.api import datastore
from google.appengine.api import datastore_types
from google.appengine.api import memcache
from google.appengine.api import namespace_manager
from google.appengine.ext.webapp.util import run_wsgi_app

# See _MakeStatResult
try:
  import posix  # pylint: disable-msg=C6204
  _stat_result = posix.stat_result
except ImportError:
  # try windows if posix isn't available (likely running tests locally on
  # windows. posix is available on app engine)
  try:
    import nt  # pylint: disable-msg=C6204
    _stat_result = nt.stat_result
  except ImportError:
    logging.warning('Could not import posix or nt, os.stat will not be '
                    'available to the target app!')

# Mount point for the virtual target file system
_TARGET_ROOT = '/target'
_TARGET_PREFIX = _TARGET_ROOT + '/'

# TODO: Need to support U and rU eventually.
_ALLOWED_FILE_MODES = frozenset(['r', 'rb', 'rU', 'U'])

# Pattern to recognize non-standard newlines
_UNIVERSAL_NEWLINE_RE = re.compile(r'\r\n?')

# Location of standard python modules.  Use the string module
# because it should always be present and is unlikely to have been
# patched.
_PYTHON_LIB_PREFIX = os.path.dirname(string.__file__) + '/'

# An error message to display when user code tries to access files that are
# matched by a static_dir or static_files handler.
_ACCESSING_STATIC_FILE_ERROR_MSG = """\
The file or directory "%s" is not accessible from scripts because it matches \
a static_dir or static_files handler in the application's app.yaml."""

# An error message to display when user code tries to access files that are
# matched by the skip_files list.
_ACCESSING_SKIPPED_FILE_ERROR_MSG = """\
The file or directory "%s" is not accessible from scripts because it matches \
the skip_files list in the application's app.yaml."""

# The mode flags returned from os.stat for files (read permission for user,
# other, group, and "regular file")
_FILE_STAT_MODE = stat.S_IROTH | stat.S_IRGRP | stat.S_IRUSR | stat.S_IFREG

# The mode flags returned from os.stat for directories (read and execute
# permissions for user, other, group, and "directory")
_DIR_STAT_MODE = (stat.S_IXOTH | stat.S_IROTH | stat.S_IXGRP | stat.S_IRGRP |
                  stat.S_IXUSR | stat.S_IRUSR | stat.S_IFDIR)


class Error(Exception):
  """Base class for TargetEnv exceptions."""
  pass


class ScriptNotFoundError(Error):
  """Raised when a specified script does not exist."""
  pass


class TargetAppError(Error):
  """Raised when target environment application exceptions are caught.

  Attributes:
    formatted_exception: Fromatted exception as returned by
                         traceback.format_exception().
  """

  def __init__(self, formatted_exception):
    Error.__init__(self)
    self._formatted_exception = formatted_exception

  def FormattedException(self):
    """Return the formatted traceback provided at initialization time."""
    return self._formatted_exception

  def __str__(self):
    return ''.join(self._formatted_exception)


def _ResolvePath(path):
  """Normalize a path and determine if it belongs in the target file system.

  Normalization always returns an absolute path with all occurences of '.'
  and '..', as well as trailing '/' removed (similar to os.path.normpath).
  In addition, if the path is a target path then it prefix of _TARGET_ROOT
  will have been removed, leaving an absolute path into the target tree.

  Examples:
    a/b          -> True,  'a/b'
    a/b/         -> True,  'a/b'
    /target/a/b  -> True,  'a/b'
    /target/a/b/ -> True,  'a/b'
    /a/b         -> False, '/a/b'
    /target      -> True,  ''
    /target/     -> True,  ''
    /            -> False, '/'
    /targetx     -> False, '/targetx'

  Args:
    path: A path string.

  Returns:
    A tuple (in_target, normalized_path) where in_target is True iff path
    belongs in the target file system and normalized_path is as described
    above.
  """
  # convert to absolute and normalize
  # TODO: This will have to change if we ever need to support chdir()
  path = os.path.normpath(os.path.join(_TARGET_ROOT, path))
  # /target is a degenerate case, pretend it was /target/
  if path == _TARGET_ROOT:
    path = _TARGET_PREFIX
  # check if path belongs to the target
  if path.startswith(_TARGET_PREFIX):
    target_path = path[len(_TARGET_PREFIX):]
    return True, target_path
  # not a target path, return the normalized path
  return False, path


def _ConvertNewlines(data):
  """Return a string with CR and CR-LF converted to LF."""
  # When data doesn't need conversion, re.search() is slightly faster than
  # re.sub().  When the data does require conversion, then surprisingly
  # two calls to replace() are a good deal faster than re.sub().  So the
  # following sequence appears to beat a call to re.sub() in typical usage.
  if _UNIVERSAL_NEWLINE_RE.search(data):
    data = data.replace('\r\n', '\n')
    data = data.replace('\r', '\n')
  return data


def _MakeStatResult(mode, size=0):
  """Creates a stat_result object given the mode and size of the file/folder.

  Note that we try to import the stat_result from both the posix and nt module
  above.

  Args:
    mode: File mode of the stat_result object to be returned.
    size: File size of the stat_result object to be returned, default 0.

  Returns:
    stat_result object with the provided values.
  """
  # posix.stat_result (and nt.stat_result) take a sequence of 10 elements, with
  # each element corresponding to a field in stat_result.
  stats = [0] * 10
  # TODO: should probably support ST_MTIME too
  stats[stat.ST_MODE] = mode
  stats[stat.ST_SIZE] = size
  return _stat_result(stats)


# TODO: File is currently patched in such a way that if the
# user opens up a non-target file the resulting object is not an
# instance of MimicFile and thus wouldn't pass a check of:
# isinstance(file(x), file).
#
# The solution requires 3 classes and multiple inheritance and is
# probably not worth it considering that user code probably won't
# open up external files in the first place, and even if it did they
# then wouldn't be checked as instances of file.


# MimicFile inherits from object first in order to make it a new-style
# class so that __new__ will work as expected.
class MimicFile(object, StringIO.StringIO):
  """A class that represents target files in Mimic."""

  def __new__(cls, *args, **kwargs):
    # This is essentially a virtual constructor, dispatching depending on
    # whether the filename is an external file or not.
    result = TargetEnvironment.Instance().OpenExternalFile(*args, **kwargs)
    if result is not None:
      # We're allowed to return instances of another class, so just return
      # the opened file, MimicFile.__init__ will not be called.
      return result
    else:
      # Instantiate a MimicFile and let __init__ do the rest.
      return super(MimicFile, cls).__new__(cls)

  def __init__(self, filename, mode='r', bufsize=-1):
    unused_bufsize = bufsize
    if mode not in _ALLOWED_FILE_MODES:
      raise IOError('Invalid mode: %s' % mode)
    contents = TargetEnvironment.Instance().ReadTargetFile(filename)
    if contents is None:
      raise IOError(errno.ENOENT, "No such file or directory: '%s'" % filename)
    if 'U' in mode:
      contents = _ConvertNewlines(contents)
    StringIO.StringIO.__init__(self, contents)

  def __enter__(self):
    # Nothing to setup
    return self

  def __exit__(self, unused_type, unused_value, unused_traceback):
    # Release StringIO memory buffer.
    self.close()
    # Allow exceptions to propagate.
    return False

  # override methods that would allow modification of the file

  def write(self, unused_data):
    raise IOError('File is read-only')

  def writelines(self, unused_sequence):
    raise IOError('File is read-only')

  def truncate(self, size=-1):
    raise IOError('File is read-only')


class _Finder(object):
  """A class finder that is bound to a specific sys.path entry.

  Attributes:
    env: A TargetEnvironment instance.
    path: The actual path entry from sys.path.
  """

  def __init__(self, env, path):
    assert path == _TARGET_ROOT
    self.env = env
    self.path = path

  def find_module(self, fullname, path=None):  # pylint: disable-msg=C6409
    """Return a loader for the requested module (see PEP 302)."""
    # The path arg is always going to be None because we aren't installed
    # on the meta_path.
    unused_path = path  # keep pylint happy
    return self.env.FindModule(self, fullname)


class _Loader(object):
  """A class loader that holds some data from find_module.

  The purpose of this class is to allow data to be conveyed from find_module
  time to load_module time.  The actual module loading code resides at
  TargetEnv.LoadModule().

  Attributes:
    env: A TargetEnvironment instance.
    path: The actual path entry from sys.path.
    file_path: A path to the file to load.
    is_pacakage: A bool that specifies if a package is being loaded.
  """

  def __init__(self, env, path, file_path, is_package):
    self.env = env
    self.path = path  # the actual sys.path entry
    self.file_path = file_path
    self.is_package = is_package

  def load_module(self, fullname):  # pylint: disable-msg=C6409
    """Load the requested module (see PEP 302)."""
    return self.env.LoadModule(self, fullname)


class TargetEnvironment(object):
  """An environment for the execution of target scripts."""

  # The currently active TargetEnvironment (there can be at most one)
  _instance = None

  @classmethod
  def Instance(cls):
    """Returns the active TargetEnvironment, or None."""
    return cls._instance

  def __init__(self, tree, config, namespace, test_portal=None):
    """Initialize and associate with a given tree.

    Args:
      tree: A mimic.common.Tree object.
      config: The app's config loaded from the app's app.yaml.
      namespace: The datastore and memcache namespace used for metadata.
      test_portal: An object that can be used to exchange data with target code
          during tests.  If this value is not None, then any loaded modules will
          be initialized with a _test_portal attribute that points to the
          supplied object.
    """
    # throws BadValueError
    namespace_manager.validate_namespace(namespace)
    self._tree = tree
    self._namespace = namespace
    self._active = False
    self._saved_sys_modules = None
    self._test_portal = test_portal
    self._saved_open = open
    self._main_method = ''
    self._wsgi_app_name = None
    self._patches = []
    self._static_file_patterns = self._CreateStaticFilePatterns(config)
    self._skip_files_pattern = self._CreateSkipFilesPattern(config)

    # TODO: separate out the patches into separate classes to reduce
    # dependency creep and clean up this class.

    # patches for builtins
    for name, value in [('open', self._CustomOpen),
                        ('file', MimicFile)]:
      self.AddPatch(patch.BuiltinPatch(name, value))
    # patches for the os module
    #
    # TODO: need to patch lstat, open, readlink, stat, walk
    for name, value in [('access', self._Access),
                        ('getcwd', self._GetCwd),
                        ('getcwdu', lambda: unicode(self._GetCwd())),
                        ('listdir', self._ListDir),
                        ('remove', self._Unlink),
                        ('rename', self._Rename),
                        ('unlink', self._Unlink),
                        ('stat', self._Stat),
                       ]:
      self.AddPatch(patch.AttributePatch(os, name, value))

    # patches for os.path
    for name, value in [('isdir', self._IsDir),
                        ('isfile', self._IsFile),
                        ('islink', self._IsLink),
                       ]:
      self.AddPatch(patch.AttributePatch(os.path, name, value))

    # patch for datastore
    self.AddPatch(composite_query.CompositeQueryPatch())

  def AddPatch(self, a_patch):
    """Add a patch that will be installed and removed automatically."""
    self._patches.append(a_patch)

  def _CreateStaticFilePatterns(self, config):
    """Creates the list of static files patterns from the given config.

    This is based loosly on StaticFileConfigMatcher in dev_appserver.py.

    Args:
      config: The app's config loaded from the app's app.yaml.

    Returns:
      A list of compiled regular expressions that will match static files.
    """
    if config is None:
      return []

    patterns = []
    handlers = config['handlers']
    for handler in handlers:
      if 'static_files' in handler:
        # See the comments in testAccess in target_env_test.py
        regex = handler['upload'] + '$'
      elif 'static_dir' in handler:
        path = handler['static_dir']
        if path[-1] == '/':
          path = path[:-1]
        # this works out to be "(folder)|(folder/(.*))", so that it matches all
        # of "folder", "folder/", and "folder/file", but not "folder_other"
        regex = r'(^{0}$)|({0}/(.*))'.format(re.escape(path))
      else:
        continue

      try:
        path_re = re.compile(regex)
      except re.error, e:
        raise target_info.ValidationError('regex "%s" in app.yaml handler does '
                                          'not compile: %s' % (regex, e))
      patterns.append(path_re)
    return patterns

  def _IsStaticFile(self, path):
    """Determines if this file is a static file, determined by the app.yaml.

    Note that it is possible to create a static_files or static_dir entry that
    will prevent mimic from accessing its own files while the target environment
    is installed.

    Args:
      path: The path as a string to test

    Returns:
      True if this path is a static file or directory, False otherwise.
    """
    if path.startswith(_TARGET_PREFIX):
      # remove the "application directory"
      path = path[len(_TARGET_PREFIX):]
    for path_re in self._static_file_patterns:
      if path_re.match(path):
        return True
    return False

  def _CreateSkipFilesPattern(self, config):
    """Creates a compiled regex to match files that should be skipped.

    This is based loosly on _RegexStrValue in validation.py.

    Args:
      config: The app's config loaded from the app's app.yaml.

    Returns:
      A compiled regex from the skip_files list in the app's app.yaml.
    """
    if config is None or 'skip_files' not in config:
      return None
    skip_files = config['skip_files']
    regex = '|'.join('(?:%s)' % skip_file for skip_file in skip_files)
    try:
      compiled_regex = re.compile(regex)
    except re.error, e:
      raise target_info.ValidationError(
          'A regex in the skip_files list in the app\'s app.yaml does not '
          'compile: %s' % e)
    return compiled_regex

  def _IsSkippedFile(self, path):
    """Determines if this file is a skipped file, determined by the app.yaml.

    This is based on parts from _IsFileAccessibleNoCache in
    dev_appserver_import_hook.py.

    Note that it is possible to create a skip_files entry that will prevent
    mimic from accessing its own files while the target environment is
    installed.

    Args:
      path: The path as a string to test

    Returns:
      True if this path should be skipped, False otherwise.
    """
    if not self._skip_files_pattern:
      return False
    if path.startswith(_TARGET_PREFIX):
      # remove the target prefix "/target/"
      path = path[len(_TARGET_PREFIX):]
    while path != os.path.dirname(path):
      if self._skip_files_pattern.match(path):
        return True
      path = os.path.dirname(path)
    return False

  def __del__(self):
    assert not self._active

  def _SetUp(self):
    """Install the TargetEnvironment (must not already be installed)."""
    assert not self._active
    assert TargetEnvironment._instance is None
    self._saved_sys_modules = sys.modules.copy()
    sys.path.insert(0, _TARGET_ROOT)
    # The order of path_hooks shouldn't matter.  The only other hook is
    # going to be the zip importer, which shouldn't interfere with this.
    # So append rather than insert since it is slightly faster.
    sys.path_hooks.append(self._PathHook)
    for p in self._patches:
      p.Install()
    self._active = True
    TargetEnvironment._instance = self

  def _TearDown(self):
    """Remove the TargetEnvironment (this call is idempotent)."""
    if not self._active:
      return
    assert TargetEnvironment._instance is self
    # Eraddicate user source, which is cached during traceback formatting.
    linecache.clearcache()
    self._CleanupModules()
    # clean up sys.path, which must be modified in place (not replaced)
    sys.path.remove(_TARGET_ROOT)
    # clean up sys.path_importer_cache
    for p in sys.path_importer_cache.keys():  # pylint: disable-msg=C6401
      if p == _TARGET_ROOT:
        del sys.path_importer_cache[p]
    sys.path_hooks.remove(self._PathHook)
    for p in self._patches:
      p.Remove()
    self._active = False
    TargetEnvironment._instance = None

  # _CleanupModules must deal with a subtle problem related to the
  # encodings module.  The decode() function relies on a registry in
  # the codecs module.  Individual encoders are implemented as
  # submodules of the encodings package.  When a new encoder is needed
  # the appropriate module is loaded under encodings and then bits of
  # that module are registered within codecs.  If that submodule is
  # cleaned up according to the normal process its refcount will hit 0
  # even though references to code within the submodule still exist in
  # the codecs module.  When a module's refcount hits 0 all entries in
  # its global dict are set to None.  This means that future
  # invocations of decode() will use stale references into code for a
  # module that is no longer valid, and exceptions similar to this
  # will be raised:
  #
  # AttributeError: 'NoneType' object has no attribute 'codecs'
  #
  # Since the encodings package has no reliance on user code, it is safe
  # to allow these to persist across target environments.  Just to be safe,
  # this approach has been extended to cover all modules coming from the
  # standard python runtime, as determined by _PYTHON_LIB_PREFIX

  def _CleanupModules(self):
    """Restore modules that were added or modified in the environment."""
    # The python interpreter holds onto a reference to sys.modules, so
    # it must be modified in-place.

    # figure out which modules need to be discarded
    dirty = set()
    for full_name, module in sys.modules.iteritems():
      # restore mimic modules which may have been masked by user code
      if full_name in self._saved_sys_modules:
        sys.modules[full_name] = self._saved_sys_modules[full_name]
        continue
      # ignore modules that are part of Python
      if (hasattr(module, '__file__') and
          module.__file__.startswith(_PYTHON_LIB_PREFIX)):
        continue
      # need to remove this module
      dirty.add(full_name)

    # get rid of the modules
    for full_name in dirty:
      module = sys.modules.pop(full_name)
      # if the module is part of a package that won't be removed, remove
      # the link from package to module
      if '.' in full_name:
        package_name, module_name = full_name.rsplit('.', 1)
        if package_name not in dirty:
          package = sys.modules.get(package_name)
          if package is None:
            # This happens if package foo imports some non-child module
            # bar and then fails during the rest of its execution.  The result
            # will be foo.bar is in sys.modules while foo is not.  We can
            # just ignore this case since there's nothing to clean up.
            continue
          package = sys.modules[package_name]
          try:
            if getattr(package, module_name) != module:
              logging.warning('cleanup of inconsistent module %s', full_name)
            delattr(package, module_name)
          except AttributeError:
            # This happens for google.appengine.ext.webapp.django and
            # google.appengine.ext.webapp.os.  The module paths don't
            # really make sense since there aren't django or os submodules
            # in webapp, but ignoring the error seems to be ok.
            pass

  def _PathHook(self, path):
    """A path hook for _TARGET_ROOT (see PEP 302)."""
    if path == _TARGET_ROOT:
      return _Finder(self, path)
    else:
      raise ImportError

  def FindModule(self, finder, fullname):
    """Return a loader for the requested module (see PEP 302).

    This method is essentially a find_module() function with the addition of a
    _Finder object that is bound to the sys.path entry that should be searched.

    Args:
      finder: A _Finder object.
      fullname: The name of the module.

    Returns:
      A _Loader object if the module can be found, otherwise None.
    """
    subdir = finder.path[len(_TARGET_ROOT):]
    partial = os.path.join(subdir, fullname.replace('.', '/'))
    # check for a package
    file_path = partial + '/__init__.py'
    if self._tree.HasFile(file_path):
      return _Loader(self, finder.path, file_path, True)
    # check for an individual file
    file_path = partial + '.py'
    if self._tree.HasFile(file_path):
      return _Loader(self, finder.path, file_path, False)
    return None

  @staticmethod
  def _FilePathToModuleName(file_path):
    """Convert a file path to a python module name."""
    name = file_path.replace('/', '.')
    if name.endswith('.py'):
      name = name[:-3]
    return name

  def LoadModule(self, loader, fullname):
    """Load the requested module (see PEP 302).

    This method is essentially a load_module() function with the addition of a
    _Loader object that conveys information determined during find_module().

    Args:
      loader: A _Loader object.
      fullname: The name of the module.

    Raises:
      AttributeError: if the requested WSGI application does not exist.

    Returns:
      A module.
    """
    # Setup the new module
    module = sys.modules.get(fullname)
    if module is not None:
      return module
    module = imp.new_module(fullname)
    module.__file__ = os.path.join(_TARGET_ROOT, loader.file_path)
    if loader.is_package:
      module.__path__ = [loader.path]
    # PEP302: __loader__ should be set to the loader object
    module.__loader__ = loader
    if self._test_portal is not None:
      module._test_portal = self._test_portal  # pylint: disable-msg=W0212

    # Get and compile the source
    source = self._tree.GetFileContents(loader.file_path)
    assert source is not None
    if self._main_method:
      # TODO: Refactor this to use a proper getattr()
      # call, rather than appending to user source code.
      source += '\n' + self._main_method
    code = compile(source, loader.file_path, 'exec')

    # Add the module to sys.modules
    module_names = [fullname]
    if fullname == '__main__':
      name = self._FilePathToModuleName(loader.file_path)
      module_names.append(name)
    for name in module_names:
      sys.modules[name] = module

    # Do this now before the first call to exec,
    # otherwise the code below that runs the wsgi app
    # will try to run the app on any imported modules
    # (because LoadModule is reentrant).
    wsgi_app_name = self._wsgi_app_name
    self._wsgi_app_name = None

    # Run the code
    try:
      exec(code, module.__dict__)  # pylint: disable-msg=W0122
    except Exception:
      for name in module_names:
        del sys.modules[name]
      raise

    # Run the WSGI app, if applicable
    if wsgi_app_name:
      if hasattr(module, wsgi_app_name):
        wsgi_app = getattr(module, wsgi_app_name)
        # let exceptions bubble up
        run_wsgi_app(wsgi_app)
      else:
        module_name = self._FilePathToModuleName(loader.file_path)
        handler = module_name + '.' + wsgi_app_name
        raise AttributeError('The WSGI application "%s" does not exist. Check '
                             'your app.yaml or %s.' % (handler,
                                                       loader.file_path))

    return module

  def OpenExternalFile(self, filename, mode='r', bufsize=-1):
    """Return an opened file, or None if the filename is for a target file."""
    in_target, path = _ResolvePath(filename)
    if in_target:
      return None
    else:
      return self._saved_open(path, mode, bufsize)

  def ReadTargetFile(self, filename):
    """Return the contents of the specified target file."""
    in_target, path = _ResolvePath(filename)
    assert in_target
    return self._tree.GetFileContents(path)

  def _CustomOpen(self, filename, mode='r', bufsize=-1):
    if self._IsStaticFile(filename):
      raise IOError(errno.ENOENT, _ACCESSING_STATIC_FILE_ERROR_MSG % filename)
    if self._IsSkippedFile(filename):
      raise IOError(errno.ENOENT, _ACCESSING_SKIPPED_FILE_ERROR_MSG % filename)
    return MimicFile(filename, mode, bufsize)

  @patch.NeedsOriginal
  def _Access(self, original, path, mode):
    """Replacement for os.access."""
    if self._IsStaticFile(path) or self._IsSkippedFile(path):
      # static files and skipped files are inaccessible to script code
      return False

    in_target, path = _ResolvePath(path)
    if in_target:
      if self._tree.HasFile(path):
        # modes W_OK and X_OK are never allowed
        return mode & (os.X_OK | os.W_OK) == 0
      elif self._tree.HasDirectory(path):
        # mode W_OK is not allowed
        return mode & os.W_OK == 0
      else:
        return False
    else:
      return original(path, mode)

  # patches for the os module

  def _GetCwd(self):
    return os.path.join(_TARGET_ROOT, self._cwd).rstrip('/')

  @patch.NeedsOriginal
  def _ListDir(self, original, path):
    use_unicode = isinstance(path, unicode)
    in_target, path = _ResolvePath(path)
    if in_target:
      entries = self._tree.ListDirectory(path)
      if not entries:
        # directories only exist by virtue of the files within them:
        raise OSError('Directory {0} does not exist'.format(path))
    else:
      entries = original(path)
      target_parent, target_name = os.path.split(_TARGET_ROOT)
      if path == target_parent:
        entries.append(target_name)
    if use_unicode:
      entries = [unicode(e) for e in entries]
    return entries

  @patch.NeedsOriginal
  def _Rename(self, original, src, dst):
    in_target, src = _ResolvePath(src)
    if in_target:
      raise OSError('Permission denied')
    in_target, dst = _ResolvePath(dst)
    if in_target:
      raise OSError('Permission denied')
    return original(src, dst)

  @patch.NeedsOriginal
  def _Unlink(self, original, path):
    """Replacement for os.unlink and os.remove."""
    in_target, path = _ResolvePath(path)
    if in_target:
      raise OSError('Permission denied')
    else:
      return original(path)

  @patch.NeedsOriginal
  def _Stat(self, original, path):
    in_target, resolved_path = _ResolvePath(path)
    if in_target:
      if self._IsStaticFile(path):
        # _IsStaticFile doesn't take paths returned from _ResolvePath, so use
        # the original path (_IsStaticFile removes _TARGET_PREFIX separately
        # from _ResolvePath)
        # Note that this will get raised even for files or directories that
        # don't exist, but whose path still match a static_dir/static_files
        # handler. Raise ENOENT and not EACCESS because when deployed, you'll
        # get ENOENT and not EACCESS.
        raise OSError(errno.ENOENT, _ACCESSING_STATIC_FILE_ERROR_MSG % path)
      elif self._IsSkippedFile(path):
        # Similar to _IsStaticFile above, use the original path
        raise OSError(errno.ENOENT, _ACCESSING_SKIPPED_FILE_ERROR_MSG % path)
      elif self._tree.HasFile(resolved_path):
        return _MakeStatResult(_FILE_STAT_MODE,
                               self._tree.GetFileSize(resolved_path))
      elif self._tree.HasDirectory(resolved_path):
        return _MakeStatResult(_DIR_STAT_MODE)
      else:
        raise OSError(errno.ENOENT, os.strerror(errno.ENOENT), resolved_path)
    else:
      # if the path is not in the target file system, defer to the original
      # os.stat (usually for absolute paths like python library files, or
      # some invalid absolute path)
      return original(resolved_path)

  # patches for os.path

  @patch.NeedsOriginal
  def _IsDir(self, original, path):
    in_target, path = _ResolvePath(path)
    if in_target:
      return self._tree.HasDirectory(path)
    else:
      return original(path)

  @patch.NeedsOriginal
  def _IsFile(self, original, path):
    in_target, path = _ResolvePath(path)
    if not path:
      return False
    if in_target:
      return self._tree.HasFile(path)
    else:
      return original(path)

  @patch.NeedsOriginal
  def _IsLink(self, original, path):
    in_target, path = _ResolvePath(path)
    if in_target:
      return False
    else:
      return original(path)

  def RunScript(self, handler, logging_handler, main_method=''):
    """Run the specified handler in the target environment.

    The target environment will be installed prior to and removed after
    script execution.  The script itself will appear to be the __main__
    module while it is executed.

    Args:
      handler: A str specifying the path to a python file in the tree or WSGI
          application
      logging_handler: A logging.Handler to be installed during script
          execution.  The logging level will temporarily be set to DEBUG.
      main_method: python code to be appended to the file source and executed.
          This can be used to automatically run a function within the compiled
          source.

    Raises:
      ScriptNotFoundError: if the specified path does not refer to a known
          file (either in the external or target file systems).
    """
    self._SetUp()
    if handler.endswith('.py'):
      # CGI handler (or WSGI done manually)
      file_path = handler
    elif '.' in handler:
      # "native" WSGI handler
      left, right = handler.rsplit('.', 1)
      file_path = '%s.py' % left.replace('.', '/')
      self._wsgi_app_name = right
    else:
      # Assume this is a package, like "foo/bar" or "foo/". Note that a package
      # that is just "foo" doesn't work and is validated in target_info.
      file_path = os.path.join(handler, '__init__.py')

    self._cwd = os.path.dirname(file_path)  # see self._GetCwd()
    sys.modules.pop('__main__', None)  # force a reload of __main__
    # prevent mimic's main.py from masking the user's main.py in the case where
    # the user's app.yaml script handler specifies a script which imports main
    sys.modules.pop('main', None)
    # force a reload of appengine_config.py, which gets automatically loaded
    # before mimic's main code
    sys.modules.pop('appengine_config', None)
    logger = logging.getLogger()
    if logging_handler:
      logger.addHandler(logging_handler)
    saved_level = logger.level
    logger.setLevel(logging.DEBUG)
    try:
      # This code relies on the fact that the os module has been patched at this
      # point and can be used to check for both external and target files.
      if not os.access(file_path, os.F_OK):
        raise ScriptNotFoundError()
      self._main_method = main_method
      # In case of an app.yaml script handler using a package script
      is_pkg = file_path.endswith('/__init__.py')
      _Loader(self, _TARGET_ROOT, file_path, is_pkg).load_module('__main__')
    except ScriptNotFoundError:
      raise
    except:
      # Materialize the traceback here, before _TearDown() is called by our
      # finally block, because here the 'open' builtin is still patched,
      # giving the formatter the ability incorporate target environment user
      # source code into the output. Without this, the offending lines of user
      # source code would not appear in the traceback or, more confusingly,
      # would be substitued by mimic's overlapping module source.
      exc_info = sys.exc_info()
      # Note format_exception relies on 'linecache', which must be reset during
      # _TearDown(), in order to prevent caching of stale user source.
      formatted_exception = traceback.format_exception(exc_info[0], exc_info[1],
                                                       exc_info[2])
      raise TargetAppError(formatted_exception)
    finally:
      self._TearDown()
      logger.setLevel(saved_level)
      logger.removeHandler(logging_handler)
