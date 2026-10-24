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
"""CsversionDumpFile walks __Csversion__ with the converted .items() calls
and writes text files; the files are real, in a temp dir."""
import os
import unittest

from . import helpers


def squeezed(path):
    """File lines with runs of whitespace collapsed; the column padding of
    the format is not what is under test."""
    with open(path) as f:
        return [' '.join(line.split()) for line in f.read().split('\n')]


def sources(*repos):
    return {'sources': dict(repos)}


GIT = ('org/repo', {'img': ('git', {'BRANCH': 'master', 'REF': 'abc123'})})
FILE = ('images', {'base': ('file', {
    'BUILD_INDEX': 3, 'SHA1': 'deadbeef', 'INJECTED': '/img/base.qcow2'})})
TAR = ('tars', {'pkgs': ('tar', {
    'BUILD_INDEX': 1, 'SHA1': 'cafe',
    'FILES': ('/opt/pkgs', ['a.txt', 'b.txt'])})})


class TestCsversionDumpFile(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.module = helpers.import_plugin('CsversionDumpFile')

    def setUp(self):
        workdir = helpers.make_tempdir(self)
        self.options = {
            'sources-file': os.path.join(workdir, 'out', 'sources.txt'),
            'version-file': os.path.join(workdir, 'version.txt'),
            'build-file': os.path.join(workdir, 'build.txt')}
        self.dumper = helpers.make_module(self.module.CsversionDumpFile)

    def dump(self, csversion, **extra):
        if csversion is not None:
            self.dumper.env.env['__Csversion__'] = csversion
        options = dict(self.options, **extra)
        return self.dumper.start__build('build', options, None, None)

    def test_start_build_dumps_git_sources(self):
        self.assertTrue(self.dump(sources(GIT)))

        self.assertEqual(
            ['git: img: REPO: org/repo BRANCH: master REF: abc123', ''],
            squeezed(self.options['sources-file']))
        self.assertEqual(1, len(self.dumper.log.called('passed')))

    def test_start_build_dumps_file_sources(self):
        self.dump(sources(FILE))

        self.assertEqual(
            ['file: base: BUILD_INDEX: 3 SHA1: deadbeef '
             'INJECTED: /img/base.qcow2', ''],
            squeezed(self.options['sources-file']))

    def test_start_build_dumps_tar_sources_with_their_file_list(self):
        self.dump(sources(TAR))

        self.assertEqual([
            'tar: pkgs: BUILD_INDEX: 1 SHA1: cafe',
            'INJECTED: /opt/pkgs',
            'a.txt',
            'b.txt',
            ''], squeezed(self.options['sources-file']))

    def test_start_build_dumps_every_repo_and_tag_in_order(self):
        two_tags = ('org/two', {
            'one': ('git', {'BRANCH': 'a', 'REF': '1'}),
            'two': ('git', {'BRANCH': 'b', 'REF': '2'})})

        self.dump(sources(GIT, two_tags))

        self.assertEqual([
            'git: img: REPO: org/repo BRANCH: master REF: abc123',
            'git: one: REPO: org/two BRANCH: a REF: 1',
            'git: two: REPO: org/two BRANCH: b REF: 2',
            ''], squeezed(self.options['sources-file']))

    def test_start_build_ignores_source_types_it_does_not_know(self):
        self.dump(sources(('pkgs', {'x': ('dpkg', {'VERSION': '1'})})))

        self.assertEqual([''], squeezed(self.options['sources-file']))

    def test_start_build_dumps_product_version_with_labels(self):
        self.dump({'product': {'metadata': {'img': {
            'name': 'Prod', 'version-full': '1.2.3',
            'description': 'The product', 'unlabelled': 'ignored'}}}})

        self.assertEqual([
            'Product information for: img',
            'PRODUCT=Prod',
            'VERSION=1.2.3',
            'PRODUCT DESCRIPTION=The product',
            ''], squeezed(self.options['version-file']))

    def test_start_build_version_tags_select_and_order_the_sections(self):
        metadata = {tag: {'name': tag.upper()} for tag in ('a', 'b', 'c')}

        self.dump({'product': {'metadata': metadata}},
                  **{'version-tags': 'c\nb,missing'})

        self.assertEqual([
            'Product information for: c', 'PRODUCT=C',
            'Product information for: b', 'PRODUCT=B',
            ''], squeezed(self.options['version-file']))
        self.assertEqual(
            [("version-tag '%s' was specified but not defined", 'missing')],
            self.dumper.log.called('warning'))

    def test_start_build_dumps_the_build_information(self):
        self.dump({'product': {'build': {'img': {
            'BUILD': '42', 'time': '2020-01-02T03:04:05Z',
            'command': 'csmake --command x'}}}})

        self.assertEqual([
            'img_BUILD_NUMBER=42',
            'img_BUILD_DATE_and_TIME=2020-01-02T03:04:05Z',
            'img_BUILD_COMMAND=csmake --command x',
            '',
            'Other information about the builds',
            ''], squeezed(self.options['build-file']))

    def test_start_build_only_writes_the_files_it_has_information_for(self):
        self.dump(sources(GIT))

        self.assertTrue(os.path.exists(self.options['sources-file']))
        self.assertFalse(os.path.exists(self.options['version-file']))
        self.assertFalse(os.path.exists(self.options['build-file']))

    def test_start_build_without_any_csversion_fails(self):
        self.assertFalse(self.dump(None))

        self.assertEqual(1, len(self.dumper.log.called('failed')))
        self.assertFalse(os.path.exists(self.options['sources-file']))

    def test_start_build_with_nothing_recorded_fails(self):
        self.assertFalse(self.dump({'unrelated': {}}))

        self.assertEqual(1, len(self.dumper.log.called('failed')))
        self.assertEqual([], self.dumper.log.called('passed'))


if __name__ == '__main__':
    unittest.main()
