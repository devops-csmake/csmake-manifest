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
"""CsversionGenerateChangeLog diffs two __Csversion__ manifests.

Most of the conversion here is iteritems() -> items() over nested manifest
dictionaries.  The module imports GitProvider (csmake-providers, which in
turn needs GitPython) and PyYAML at import time; the tests skip when either
is unavailable.  The git-specific change analysis is not exercised, because
it fetches from remote repositories.
"""
import os
import unittest
import types

from . import helpers


def dpkg(version):
    return ('dpkg', {'PACKAGE': 'x', 'VERSION': version, 'ARCH': ''})


class TestCsversionGenerateChangeLog(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.module = helpers.import_plugin('CsversionGenerateChangeLog')
        import yaml
        cls.yaml = yaml

    def changelog_module(self, **attrs):
        return helpers.make_module(
            self.module.CsversionGenerateChangeLog, **attrs)

    def test_product_diff_reports_build_and_metadata_changes(self):
        previous = {'product': {
            'build': {'img': {'command': 'csmake a', 'time': 't0'}},
            'metadata': {'img': {
                'name': 'Prod', 'version-full': '1.0', 'dropped': 'x'}}}}
        current = {'product': {
            'build': {'img': {'command': 'csmake b'},
                      'other': {'command': 'csmake c'}},
            'metadata': {
                'img': {'name': 'Prod', 'version-full': '1.1', 'added': 'y'},
                'other': {'name': 'Other'}}}}
        changelog = {}

        self.changelog_module()._createProductDiff(
            changelog, previous, current)

        build = changelog['product']['build']
        self.assertEqual(current['product']['build'], build['new'])
        self.assertEqual(previous['product']['build'], build['old'])
        self.assertEqual(
            ["NOTE: Build: img Command line changed",
             "Build other, previous didn't have a command"],
            build['__info'])
        self.assertEqual({
            'img': {
                'version-full': {'new': '1.1', 'old': '1.0'},
                'added': {'new': 'y', 'old': ''},
                'dropped': {'new': '', 'old': 'x'}},
            'other': {'__info': ['build in current and not in previous']}},
            changelog['product']['metadata'])

    def test_sources_diff_reports_only_what_changed(self):
        previous = {'sources': {
            'bash': {'img': dpkg('5.0')},
            'libc6': {'img_amd64': dpkg('2.31')}}}
        current = {'sources': {
            'bash': {'img': dpkg('5.1')},
            'libc6': {'img_amd64': dpkg('2.31')},
            'newpkg': {'img': dpkg('1.0')}}}
        changelog = {}

        self.changelog_module()._createSourcesDiff(
            changelog, previous, current)

        self.assertEqual({
            'bash': {
                'new': {'img': dpkg('5.1')},
                'old': {'img': dpkg('5.0')},
                '__info': ["Build: img, version changed from '5.0' to '5.1'"]},
            'newpkg': {
                'new': {'img': dpkg('1.0')},
                'old': {},
                '__info': ['source was not in previous']}},
            changelog['sources'])

    def test_build_reads_manifests_and_writes_a_yaml_changelog(self):
        workdir = helpers.make_tempdir(self)
        previous = os.path.join(workdir, 'previous.yaml')
        output = os.path.join(workdir, 'changelog.yaml')
        with open(previous, 'w') as f:
            f.write(self.yaml.safe_dump({
                'sources': {'bash': {'img': dpkg('5.0')}},
                'product': {
                    'build': {'img': {'command': 'csmake a'}},
                    'metadata': {'img': {'version-full': '1.0'}}}}))
        mapping = types.SimpleNamespace(iterspecs=lambda: [
            ([{'id': 'previous', 'location': previous}],
             [{'type': 'yaml', 'location': output}])])
        module = self.changelog_module(mapping=mapping)
        module.env.env['RESULTS'] = workdir
        module.env.env['__Csversion__'] = {
            'sources': {'bash': {'img': dpkg('5.1')}},
            'product': {
                'build': {'img': {'command': 'csmake a'}},
                'metadata': {'img': {'version-full': '1.1'}}}}

        self.assertTrue(module.build({}))

        with open(output) as f:
            changelog = self.yaml.safe_load(f)
        self.assertEqual(
            ["Build: img, version changed from '5.0' to '5.1'"],
            changelog['sources']['bash']['__info'])
        self.assertEqual(
            {'img': {'version-full': {'new': '1.1', 'old': '1.0'}}},
            changelog['product']['metadata'])
        self.assertEqual(1, len(module.log.called('passed')))


if __name__ == '__main__':
    unittest.main()
