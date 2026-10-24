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
"""Test-only shim so plugin modules' 'from Csmake.X import Y' resolves.

The installed csmake only ships CsmakeCore, while plugin modules still import
'Csmake.<name>'.  That mismatch is a known ecosystem issue outside the scope
of these tests, so install() aliases Csmake -> CsmakeCore (same module
objects, so class identity is preserved) without touching production imports.
"""
import importlib
import importlib.abc
import importlib.util
import os
import sys
import unittest

_WORK_DIR = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))


def add_sibling_checkout(name):
    """Append <repo parent>/<name> to sys.path if such a checkout exists."""
    path = os.path.join(_WORK_DIR, name)
    if os.path.isdir(path) and path not in sys.path:
        sys.path.append(path)


class _CsmakeAliasFinder(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.startswith('Csmake.'):
            return importlib.util.spec_from_loader(fullname, self)
        return None

    def create_module(self, spec):
        return importlib.import_module(
            'CsmakeCore.' + spec.name[len('Csmake.'):])

    def exec_module(self, module):
        pass


def install():
    try:
        importlib.import_module('Csmake')
        return
    except ImportError:
        pass
    try:
        core = importlib.import_module('CsmakeCore')
    except ImportError:
        add_sibling_checkout('csmake')
        try:
            core = importlib.import_module('CsmakeCore')
        except ImportError:
            raise unittest.SkipTest("csmake core not found")
    sys.modules['Csmake'] = core
    sys.meta_path.insert(0, _CsmakeAliasFinder())
