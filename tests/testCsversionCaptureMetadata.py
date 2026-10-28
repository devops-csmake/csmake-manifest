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
"""CsversionCaptureMetadata sorts the section's options into product
metadata (version_*) and build (build_*) records; the loop over the options
is the converted .items() call.  The section metadata and the clock are
replaced by fakes, so the timestamp is deterministic."""
import datetime
import sys
import types
import unittest
from unittest import mock

from . import helpers

BUILT_AT = '2024-01-02T03:04:05Z'


class TestCsversionCaptureMetadata(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.module = helpers.import_plugin('CsversionCaptureMetadata')

    def setUp(self):
        metadata = types.SimpleNamespace(
            _getMetadataDefinitions=lambda: {'name': 'Prod'},
            _getDefaultDefinedVersion=lambda: '1.2.3')
        self.capture = helpers.make_module(
            self.module.CsversionCaptureMetadata, metadata=metadata)
        clock = types.SimpleNamespace(
            utcnow=lambda: datetime.datetime(2024, 1, 2, 3, 4, 5, 678901))
        patcher = mock.patch.object(self.module, 'datetime', clock)
        patcher.start()
        self.addCleanup(patcher.stop)

    def product(self):
        return self.capture.env.env['__Csversion__']['product']

    def test_build_records_version_and_build_options(self):
        self.assertTrue(self.capture.build({
            'tag': 'img',
            'version_description': ' A product ',
            'build_BUILD': '42',
            'unrelated': 'ignored'}))

        self.assertEqual(
            {'img': {'name': 'Prod', 'version-full': '1.2.3',
                     'description': 'A product'}},
            self.product()['metadata'])
        self.assertEqual(
            {'img': {'time': BUILT_AT,
                     'command': ' '.join(sys.argv),
                     'BUILD': '42'}},
            self.product()['build'])
        self.assertEqual(1, len(self.capture.log.called('passed')))

    def test_build_ignores_blank_options(self):
        self.capture.build({
            'tag': 'img', 'version_blank': '   ', 'build_blank': ''})

        self.assertNotIn('blank', self.product()['metadata']['img'])
        self.assertNotIn('blank', self.product()['build']['img'])

    def test_build_keeps_other_tags_and_warns_when_a_tag_is_redone(self):
        self.capture.build({'tag': 'one', 'build_BUILD': '1'})
        self.capture.build({'tag': 'two', 'build_BUILD': '2'})
        self.assertEqual([], self.capture.log.called('warning'))

        self.capture.build({'tag': 'one', 'build_BUILD': '3'})

        self.assertEqual({'one', 'two'}, set(self.product()['build']))
        self.assertEqual('3', self.product()['build']['one']['BUILD'])
        self.assertEqual(2, len(self.capture.log.called('warning')))

    def test_build_amend_adds_to_the_existing_records(self):
        self.capture.build({'tag': 'img', 'build_BUILD': '42'})

        self.assertTrue(self.capture.build({
            'tag': 'img', 'amend': 'True',
            'version_extra': 'more', 'build_WRAPPER': 'w'}))

        self.assertEqual(
            {'name': 'Prod', 'version-full': '1.2.3', 'extra': 'more'},
            self.product()['metadata']['img'])
        self.assertEqual(
            {'time': BUILT_AT, 'command': ' '.join(sys.argv),
             'BUILD': '42', 'WRAPPER': 'w'},
            self.product()['build']['img'])

    def test_build_amend_without_any_metadata_fails(self):
        self.assertIsNone(self.capture.build(
            {'tag': 'img', 'amend': 'True', 'version_extra': 'x'}))

        self.assertEqual(1, len(self.capture.log.called('failed')))
        self.assertEqual([], self.capture.log.called('passed'))

    def test_build_amend_of_an_unknown_tag_fails(self):
        self.capture.build({'tag': 'img'})

        self.assertIsNone(self.capture.build(
            {'tag': 'other', 'amend': 'True', 'version_extra': 'x'}))

        self.assertEqual(1, len(self.capture.log.called('failed')))
        self.assertNotIn('other', self.product()['metadata'])

    def test_build_amend_other_than_true_replaces_the_records(self):
        self.capture.build({'tag': 'img', 'build_BUILD': '42'})

        self.capture.build({'tag': 'img', 'amend': 'False', 'build_X': '1'})

        self.assertNotIn('BUILD', self.product()['build']['img'])
        self.assertEqual('1', self.product()['build']['img']['X'])


if __name__ == '__main__':
    unittest.main()
