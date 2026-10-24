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
"""Shared helpers for the csmake-manifest tests.

The plugin modules are CsmakeModule subclasses, which need a whole csmake
engine to construct.  The methods under test only touch self.env, self.log
and a few helpers inherited from the base class, so the tests build the
object with object.__new__() and attach just those attributes (make_module).
"""
import importlib
import os
import shutil
import stat
import tempfile
import types
import unittest
from unittest import mock

from . import csmake_alias


# Import failures on these top-level names mean a dependency that lives
# outside this repo is missing (csmake core, csmake-providers, GitPython,
# PyYAML) and the test is skipped.  Any other ImportError, such as a stdlib
# module that no longer exists under Python 3, is a real failure.
EXTERNAL_DEPENDENCIES = (
    'Csmake', 'CsmakeCore', 'CsmakeProviders', 'CsmakeModules',
    'git', 'gitdb', 'yaml')


def import_plugin(name):
    """Import CsmakeModules.<name>, or skip when a dependency is missing."""
    csmake_alias.install()
    csmake_alias.add_sibling_checkout('csmake-providers')
    fullname = 'CsmakeModules.' + name
    try:
        return importlib.import_module(fullname)
    except ImportError as e:
        missing = e.name or ''
        if missing != fullname and \
                missing.split('.')[0] in EXTERNAL_DEPENDENCIES:
            raise unittest.SkipTest(
                "cannot import %s: %s" % (fullname, e))
        raise


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


# Stand-in for 'sudo -E chroot <root> <command...>'.  It needs neither root
# nor a real chroot: the command just runs with <root> as its working
# directory, and absolute 'source /x' paths in a 'bash -c' script are mapped
# to <root>/x, which is where a chroot would have found them.  The caller's
# own VIRTUAL_ENV does not exist inside the chroot, so it is dropped.
FAKE_SUDO = r'''#!/bin/bash
while [ "$1" = "-E" ]; do shift; done
if [ "$1" != "chroot" ]; then
    echo "fake sudo: unexpected arguments: $*" >&2
    exit 97
fi
shift
root="$1"
shift
cd "$root" || exit 98
unset VIRTUAL_ENV
if [ "$1" = "/bin/bash" ] && [ "$2" = "-c" ]; then
    script=$(printf '%s' "$3" | sed "s#source /#source $root/#g")
    exec /bin/bash -c "$script"
fi
exec "$@"
'''


def write_file(path, text, executable=False):
    directory = os.path.dirname(path)
    if directory and not os.path.isdir(directory):
        os.makedirs(directory)
    with open(path, 'w') as f:
        f.write(text)
    if executable:
        os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR | stat.S_IXGRP)


def install_fake_chroot_tools(testcase):
    """Put a fake 'sudo' first on PATH; returns (bin_dir, chroot_dir).

    Further fake executables (dpkg-query, pip, ...) can be written into
    bin_dir by the caller, and are found by the fake sudo through PATH.
    """
    bin_dir = make_tempdir(testcase)
    chroot_dir = make_tempdir(testcase)
    write_file(os.path.join(bin_dir, 'sudo'), FAKE_SUDO, executable=True)
    patcher = mock.patch.dict(
        os.environ,
        {'PATH': bin_dir + os.pathsep + os.environ.get('PATH', os.defpath)})
    patcher.start()
    testcase.addCleanup(patcher.stop)
    return bin_dir, chroot_dir
