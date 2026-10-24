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
"""CsversionGenerateYAMLManifest dumps __Csversion__ to YAML files.

The migration only removed an unused 'import urlparse' here, so these are
minimal checks that the module still imports and does its job: the output
locations are resolved against RESULTS, and the YAML text goes to each file.
"""
import os
import types
import unittest

from . import helpers

CSVERSION = {
    'sources': {'bash': {'img': ('dpkg', {'VERSION': '5.1', 'ARCH': ''})}},
    'product': {'build': {'img': {'BUILD': '42'}}}}


class TestCsversionGenerateYAMLManifest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.module = helpers.import_plugin('CsversionGenerateYAMLManifest')
        import yaml
        cls.yaml = yaml

    def setUp(self):
        self.workdir = helpers.make_tempdir(self)
        self.results = os.path.join(self.workdir, 'results')
        os.makedirs(self.results)

    def generator(self, locations, csversion=CSVERSION):
        yieldsfiles = None
        if locations is not None:
            yieldsfiles = [{'location': loc} for loc in locations]
        generator = helpers.make_module(
            self.module.CsversionGenerateYAMLManifest,
            yieldsfiles=yieldsfiles)
        generator.env.env['RESULTS'] = self.results
        if csversion is not None:
            generator.env.env['__Csversion__'] = csversion
        return generator

    def test_build_writes_the_yaml_to_a_location_under_results(self):
        generator = self.generator(['manifest.yaml'])

        result = generator.build({})

        self.assertEqual(self.yaml.safe_dump(CSVERSION), result)
        with open(os.path.join(self.results, 'manifest.yaml')) as f:
            self.assertEqual(result, f.read())
        self.assertEqual(1, len(generator.log.called('passed')))

    def test_build_writes_absolute_locations_as_they_are(self):
        target = os.path.join(self.workdir, 'elsewhere.yaml')

        self.generator([target]).build({})

        self.assertTrue(os.path.exists(target))
        self.assertEqual([], os.listdir(self.results))

    def test_build_writes_dot_slash_locations_relative_to_the_cwd(self):
        previous = os.getcwd()
        os.chdir(self.workdir)
        self.addCleanup(os.chdir, previous)

        self.generator(['./here.yaml']).build({})

        self.assertTrue(os.path.exists(os.path.join(self.workdir, 'here.yaml')))

    def test_build_writes_every_location(self):
        self.generator(['one.yaml', 'two.yaml']).build({})

        self.assertEqual(
            ['one.yaml', 'two.yaml'], sorted(os.listdir(self.results)))

    def test_build_yaml_reads_back_as_the_recorded_state(self):
        self.generator(['manifest.yaml']).build({})

        with open(os.path.join(self.results, 'manifest.yaml')) as f:
            loaded = self.yaml.safe_load(f)
        self.assertEqual(
            ['dpkg', {'VERSION': '5.1', 'ARCH': ''}],
            loaded['sources']['bash']['img'])
        self.assertEqual(CSVERSION['product'], loaded['product'])

    def test_build_without_yields_files_does_nothing(self):
        generator = self.generator(None)

        self.assertIsNone(generator.build({}))

        self.assertEqual(1, len(generator.log.called('passed')))
        self.assertEqual([], os.listdir(self.results))

    def test_build_with_no_yields_files_entries_does_nothing(self):
        generator = self.generator([])

        self.assertIsNone(generator.build({}))

        self.assertEqual(1, len(generator.log.called('passed')))

    def test_build_without_recorded_state_writes_nothing(self):
        generator = self.generator(['manifest.yaml'], csversion=None)

        self.assertIsNone(generator.build({}))

        self.assertEqual([], os.listdir(self.results))
        self.assertEqual(1, len(generator.log.called('warning')))


if __name__ == '__main__':
    unittest.main()
