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
"""CsversionCollectDpkgs parses 'dpkg-query' output run through sudo/chroot.

Under Python 3 Popen().communicate() returns bytes unless a text mode is
requested, and out.split('\\n') then raises TypeError.  subprocess.Popen is
replaced by helpers.FakePopen, which returns bytes unless the module asks for
text, so the module has to ask for it to get anything parsed.
"""
import unittest

from . import helpers
from .helpers import popen_result

DPKG_FORMAT = '${binary:Package} (${Version})\\n'


def dpkg(package, version, arch=''):
    return ('dpkg', {'PACKAGE': package, 'VERSION': version, 'ARCH': arch})


class TestCsversionCollectDpkgs(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.module = helpers.import_plugin('CsversionCollectDpkgs')

    def build(self, *results, **options):
        """Run build() with Popen scripted to return results."""
        options.setdefault('tag', 'img')
        options.setdefault('chroot', '/mnt/chroot')
        collector = helpers.make_module(self.module.CsversionCollectDpkgs)
        popen = helpers.patch_popen(self, self.module, *results)
        return collector, popen, collector.build(options)

    def test_build_records_each_package_with_its_version(self):
        collector, _, result = self.build(popen_result(
            'bash (5.1-2+deb11u1)\n'
            'tzdata (2021a-1+deb11u7)\n'))

        self.assertEqual({
            'bash': {'img': dpkg('bash', '5.1-2+deb11u1')},
            'tzdata': {'img': dpkg('tzdata', '2021a-1+deb11u7')}}, result)
        self.assertIs(result, collector.env.env['__Csversion__']['sources'])
        self.assertEqual(1, len(collector.log.called('passed')))

    def test_build_tags_multiarch_packages_with_their_architecture(self):
        _, _, result = self.build(popen_result(
            'libc6:amd64 (2.31-13+deb11u5)\n'
            'libc6:i386 (2.31-13+deb11u5)\n'))

        self.assertEqual({'libc6': {
            'img_amd64': dpkg('libc6', '2.31-13+deb11u5', 'amd64'),
            'img_i386': dpkg('libc6', '2.31-13+deb11u5', 'i386')}}, result)

    def test_build_queries_dpkg_in_the_chroot_through_sudo(self):
        _, popen, _ = self.build(popen_result('bash (5.1)\n'),
                                 chroot='/mnt/image')

        self.assertEqual(1, len(popen.calls))
        args, kwargs = popen.calls[0]
        self.assertEqual(
            ['sudo', '-E', 'chroot', '/mnt/image',
             'dpkg-query', '--show', '-f', DPKG_FORMAT], args)
        self.assertFalse(kwargs.get('shell'))

    def test_build_skips_blank_and_unrecognised_lines(self):
        collector, _, result = self.build(popen_result(
            '\n'
            'not a package line\n'
            'bash (5.1)\n'
            '\n'))

        self.assertEqual({'bash': {'img': dpkg('bash', '5.1')}}, result)
        self.assertEqual(
            [("Didn't match: %s", 'not a package line')],
            collector.log.called('debug'))

    def test_build_with_no_output_records_nothing(self):
        collector, _, result = self.build(popen_result('', 'E: no such chroot\n', 1))

        self.assertEqual({}, result)

    def test_build_decodes_non_ascii_output(self):
        _, _, result = self.build(popen_result(
            u'café (1.0-é)\n'.encode('utf-8')))

        self.assertEqual({u'café': {'img': dpkg(u'café', u'1.0-é')}},
                         result)

    def test_build_accepts_windows_line_endings(self):
        _, _, result = self.build(popen_result('bash (5.1)\r\ntzdata (2021a)\r\n'))

        self.assertEqual({'bash', 'tzdata'}, set(result))
        self.assertEqual('5.1', result['bash']['img'][1]['VERSION'])

    def test_build_same_package_listed_twice_warns_and_keeps_the_last(self):
        collector, _, result = self.build(popen_result(
            'bash (5.0)\nbash (5.1)\n'))

        self.assertEqual({'bash': {'img': dpkg('bash', '5.1')}}, result)
        self.assertEqual(1, len(collector.log.called('warning')))

    def test_build_adds_to_sources_already_recorded(self):
        collector = helpers.make_module(self.module.CsversionCollectDpkgs)
        collector.env.env['__Csversion__'] = {
            'sources': {'bash': {'older': dpkg('bash', '4.4')}}}
        helpers.patch_popen(self, self.module, popen_result('bash (5.1)\n'))

        result = collector.build({'tag': 'img', 'chroot': '/mnt/chroot'})

        self.assertEqual(
            {'older': dpkg('bash', '4.4'), 'img': dpkg('bash', '5.1')},
            result['bash'])


if __name__ == '__main__':
    unittest.main()
