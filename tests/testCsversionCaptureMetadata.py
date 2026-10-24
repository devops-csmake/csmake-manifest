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
is the converted .items() call.  Only the clock is replaced, so the
timestamp is deterministic."""
import datetime
import sys
import types
import unittest
from unittest import mock

from . import helpers


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

    def test_version_and_build_options_are_recorded(self):
        self.assertTrue(self.capture.build({
            'tag': 'img',
            'version_description': ' A product ',
            'version_blank': '   ',
            'build_BUILD': '42',
            'build_blank': '',
            'unrelated': 'ignored'}))

        self.assertEqual(
            {'img': {'name': 'Prod', 'version-full': '1.2.3',
                     'description': 'A product'}},
            self.product()['metadata'])
        self.assertEqual(
            {'img': {'time': '2024-01-02T03:04:05Z',
                     'command': ' '.join(sys.argv),
                     'BUILD': '42'}},
            self.product()['build'])

    def test_amend_adds_to_the_existing_records(self):
        self.capture.build({'tag': 'img', 'build_BUILD': '42'})

        self.assertTrue(self.capture.build({
            'tag': 'img', 'amend': 'True',
            'version_extra': 'more', 'build_WRAPPER': 'w'}))

        self.assertEqual(
            {'name': 'Prod', 'version-full': '1.2.3', 'extra': 'more'},
            self.product()['metadata']['img'])
        self.assertEqual(
            {'time': '2024-01-02T03:04:05Z', 'command': ' '.join(sys.argv),
             'BUILD': '42', 'WRAPPER': 'w'},
            self.product()['build']['img'])


if __name__ == '__main__':
    unittest.main()
