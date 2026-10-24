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
"""CsversionCollectDpkgs / CsversionCollectPips parse subprocess output.

Under Python 3 Popen().communicate() returns bytes unless
universal_newlines=True, and out.split('\\n') then raises TypeError.  These
tests run the real modules against fake 'sudo', 'dpkg-query' and 'pip'
executables placed first on PATH (see helpers.install_fake_chroot_tools), so
real subprocesses produce the output that gets parsed.
"""
import os
import unittest

from . import helpers

FAKE_DPKG_QUERY = r'''#!/bin/bash
here=$(dirname "$0")
{ pwd -P; for arg in "$@"; do printf '%s\n' "$arg"; done; } \
    > "$here/dpkg-query.invocation"
cat "$here/dpkg-query.out"
'''

# Picks its output by the virtual environment the shell has activated,
# exactly as the module relies on 'source <venv>/bin/activate' doing.
FAKE_PIP = r'''#!/bin/bash
[ "$1" = "list" ] || exit 2
here=$(dirname "$0")
venv=__global
[ -n "$VIRTUAL_ENV" ] && venv=$(basename "$VIRTUAL_ENV")
cat "$here/pip.$venv.out"
'''

FAKE_ACTIVATE = '''export VIRTUAL_ENV=%s
deactivate() { unset VIRTUAL_ENV; }
'''


class TestCsversionCollectDpkgs(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.module = helpers.import_plugin('CsversionCollectDpkgs')

    def test_parses_dpkg_query_output_from_chroot(self):
        bin_dir, chroot = helpers.install_fake_chroot_tools(self)
        helpers.write_file(
            os.path.join(bin_dir, 'dpkg-query'), FAKE_DPKG_QUERY,
            executable=True)
        helpers.write_file(
            os.path.join(bin_dir, 'dpkg-query.out'),
            'bash (5.1-2+deb11u1)\n'
            'libc6:amd64 (2.31-13+deb11u5)\n'
            'libc6:i386 (2.31-13+deb11u5)\n'
            'not a package line\n'
            '\n'
            'tzdata (2021a-1+deb11u7)\n')
        collector = helpers.make_module(self.module.CsversionCollectDpkgs)

        result = collector.build({'tag': 'img', 'chroot': chroot})

        self.assertEqual({
            'bash': {'img': ('dpkg', {
                'PACKAGE': 'bash', 'VERSION': '5.1-2+deb11u1', 'ARCH': ''})},
            'libc6': {
                'img_amd64': ('dpkg', {
                    'PACKAGE': 'libc6', 'VERSION': '2.31-13+deb11u5',
                    'ARCH': 'amd64'}),
                'img_i386': ('dpkg', {
                    'PACKAGE': 'libc6', 'VERSION': '2.31-13+deb11u5',
                    'ARCH': 'i386'})},
            'tzdata': {'img': ('dpkg', {
                'PACKAGE': 'tzdata', 'VERSION': '2021a-1+deb11u7',
                'ARCH': ''})},
        }, result)
        self.assertIs(result, collector.env.env['__Csversion__']['sources'])
        self.assertEqual(1, len(collector.log.called('passed')))
        # the query really ran inside the requested chroot
        with open(os.path.join(bin_dir, 'dpkg-query.invocation')) as f:
            cwd, args = f.read().split('\n', 1)
        self.assertEqual(os.path.realpath(chroot), cwd)
        self.assertEqual(
            ['--show', '-f', '${binary:Package} (${Version})\\n'],
            args.rstrip('\n').split('\n'))


class TestCsversionCollectPips(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.module = helpers.import_plugin('CsversionCollectPips')

    def setUp(self):
        self.bin_dir, self.chroot = helpers.install_fake_chroot_tools(self)
        helpers.write_file(
            os.path.join(self.bin_dir, 'pip'), FAKE_PIP, executable=True)
        self.collector = helpers.make_module(self.module.CsversionCollectPips)

    def add_venv(self, venv):
        """Create <chroot><venv> the way virtualenv lays it out."""
        helpers.write_file(
            os.path.join(self.chroot + venv, 'bin', 'activate_this.py'), '')
        helpers.write_file(
            os.path.join(self.chroot + venv, 'bin', 'activate'),
            FAKE_ACTIVATE % venv)

    def set_pip_list(self, name, text):
        helpers.write_file(
            os.path.join(self.bin_dir, 'pip.%s.out' % name), text)

    def test_global_pip_list_is_parsed_when_there_are_no_virtualenvs(self):
        self.set_pip_list(
            '__global',
            'pip (9.0.1)\n'
            'setuptools (36.0.1)\n'
            '\n'
            'You are using pip version 9.0.1, however 9.0.3 is available.\n')

        result = self.collector.build({'tag': 'img', 'chroot': self.chroot})

        self.assertEqual({
            'pip': {'img___global': ('pip', {
                'VENV': '__global', 'PACKAGE': 'pip', 'VERSION': '9.0.1'})},
            'setuptools': {'img___global': ('pip', {
                'VENV': '__global', 'PACKAGE': 'setuptools',
                'VERSION': '36.0.1'})},
        }, result)
        self.assertEqual(1, len(self.collector.log.called('passed')))

    def test_virtualenvs_are_found_and_listed_separately(self):
        self.add_venv('/opt/venvA')
        self.add_venv('/srv/app/venvB')
        self.set_pip_list('__global', 'pip (9.0.1)\n')
        self.set_pip_list('venvA', 'Flask (0.12.2)\npip (9.0.3)\n')
        self.set_pip_list('venvB', 'requests (2.18.4)\n')

        result = self.collector.build({'tag': 'img', 'chroot': self.chroot})

        self.assertEqual({'pip', 'Flask', 'requests'}, set(result))
        self.assertEqual(
            {'img___global': ('pip', {
                'VENV': '__global', 'PACKAGE': 'pip', 'VERSION': '9.0.1'}),
             'img_/opt/venvA': ('pip', {
                'VENV': '/opt/venvA', 'PACKAGE': 'pip', 'VERSION': '9.0.3'})},
            result['pip'])
        self.assertEqual(
            {'img_/opt/venvA': ('pip', {
                'VENV': '/opt/venvA', 'PACKAGE': 'Flask',
                'VERSION': '0.12.2'})},
            result['Flask'])
        self.assertEqual(
            {'img_/srv/app/venvB': ('pip', {
                'VENV': '/srv/app/venvB', 'PACKAGE': 'requests',
                'VERSION': '2.18.4'})},
            result['requests'])


if __name__ == '__main__':
    unittest.main()
