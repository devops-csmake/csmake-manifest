# <copyright>
# (c) Copyright 2026 Autumn Patterson
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or (at your
# option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
# </copyright>
"""Shared helpers for the csmake-manifest unit tests.

The plugin modules are CsmakeModule subclasses, which need a whole csmake
engine to construct.  The methods under test only touch self.env, self.log
and a few helpers inherited from the base class, so the tests build the
object with object.__new__() and attach just those attributes (make_module).

External boundaries (subprocess, GitPython, csmake-providers) are replaced
with fakes that honour the real API's type contract; see FakePopen.
"""
import importlib
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

from . import csmake_alias


# Import failures on these top-level names mean a dependency that lives
# outside this repo is missing (csmake core, GitPython, PyYAML) and the test
# is skipped.  Any other ImportError, such as a stdlib module that no longer
# exists under Python 3, is a real failure.
EXTERNAL_DEPENDENCIES = (
    'Csmake', 'CsmakeCore', 'CsmakeProviders', 'CsmakeModules',
    'git', 'gitdb', 'yaml')


def import_plugin(name, stubs=None):
    """Import CsmakeModules.<name> afresh, or skip when a dependency is missing.

    stubs maps module names to stand-in modules that are installed in
    sys.modules for the duration of the import only, so that a plugin's
    'import git' or 'from CsmakeProviders.GitProvider import ...' binds the
    stub whether or not the real package is installed.
    """
    csmake_alias.install()
    fullname = 'CsmakeModules.' + name
    stubs = dict(stubs or {})
    keys = list(stubs) + [fullname]
    saved = dict((key, sys.modules.get(key)) for key in keys)
    sys.modules.pop(fullname, None)
    sys.modules.update(stubs)
    try:
        return importlib.import_module(fullname)
    except ImportError as e:
        missing = e.name or ''
        if missing != fullname and \
                missing.split('.')[0] in EXTERNAL_DEPENDENCIES:
            raise unittest.SkipTest(
                "cannot import %s: %s" % (fullname, e))
        raise
    finally:
        for key, module in saved.items():
            if module is None:
                sys.modules.pop(key, None)
            else:
                sys.modules[key] = module


class FakeLog(object):
    """Records every log call (passed, info, warning, ...) by name."""

    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        if name.startswith('__'):
            raise AttributeError(name)

        def record(*args, **kwargs):
            self.calls.append((name, args))
        return record

    def called(self, name):
        return [args for (n, args) in self.calls if n == name]


def make_module(cls, **attrs):
    """An instance of a CsmakeModule/CsmakeAspect subclass without an engine."""
    module = object.__new__(cls)
    module.env = types.SimpleNamespace(env={})
    module.log = FakeLog()
    for key, value in attrs.items():
        setattr(module, key, value)
    return module


def make_tempdir(testcase):
    path = tempfile.mkdtemp(prefix='csmanifest-test-')
    testcase.addCleanup(shutil.rmtree, path, True)
    return path


class FakeProcess(object):
    """What Popen returns.  Like the real one, returncode stays None until
    communicate() has run, and a stream that was not piped comes back None."""

    def __init__(self, out, err, exit_status):
        self.returncode = None
        self._out = out
        self._err = err
        self._exit_status = exit_status

    def communicate(self, input=None, timeout=None):
        self.returncode = self._exit_status
        return self._out, self._err


def _stream(data, piped, text):
    """The type contract of Popen.communicate(): bytes unless a text mode was
    requested (universal_newlines / text / encoding / errors), then str with
    universal newlines applied."""
    if not piped:
        return None
    if text:
        if isinstance(data, bytes):
            data = data.decode('utf-8')
        return data.replace('\r\n', '\n').replace('\r', '\n')
    if isinstance(data, str):
        data = data.encode('utf-8')
    return data


def popen_result(stdout='', stderr='', returncode=0):
    return (stdout, stderr, returncode)


class FakePopen(object):
    """Scripted stand-in for subprocess.Popen.

    Each call consumes the next scripted popen_result() (or raises it, when
    it is an exception).  Output scripted as str is encoded to bytes unless
    the caller asked for text, so a caller that forgot universal_newlines
    gets bytes, exactly as with the real thing.  Every call is recorded in
    .calls as (args, kwargs).
    """

    def __init__(self, *results):
        self.results = list(results)
        self.calls = []

    def __call__(self, args, **kwargs):
        self.calls.append((args, kwargs))
        if not self.results:
            raise AssertionError("unexpected Popen call: %r" % (args,))
        result = self.results.pop(0)
        if isinstance(result, BaseException):
            raise result
        stdout, stderr, returncode = result
        text = bool(kwargs.get('universal_newlines') or kwargs.get('text')
                    or kwargs.get('encoding') or kwargs.get('errors'))
        return FakeProcess(
            _stream(stdout, kwargs.get('stdout') == subprocess.PIPE, text),
            _stream(stderr, kwargs.get('stderr') == subprocess.PIPE, text),
            returncode)


def patch_popen(testcase, module, *results):
    """Replace the 'subprocess' a plugin module uses with one whose Popen is a
    FakePopen scripted with results; returns the FakePopen."""
    fake = FakePopen(*results)
    patched = types.SimpleNamespace(Popen=fake, PIPE=subprocess.PIPE)
    patcher = mock.patch.object(module, 'subprocess', patched)
    patcher.start()
    testcase.addCleanup(patcher.stop)
    return fake
