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
"""CsversionHLinuxConfigApt copies the options of an HLinuxConfigApt section
into __Csversion__.  The migration only removed an unused 'import urlparse'
here, so these are minimal checks that the aspect still imports and works."""
import types
import unittest

from . import helpers


class TestCsversionHLinuxConfigApt(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.module = helpers.import_plugin('CsversionHLinuxConfigApt')

    def aspect(self):
        return helpers.make_module(self.module.CsversionHLinuxConfigApt)

    def end_build(self, aspect, tag='img', **hlinux_options):
        return aspect.end__build(
            'build', {'tag': tag}, None, hlinux_options)

    def test_end_build_records_the_section_options_under_the_tag(self):
        aspect = self.aspect()

        self.assertTrue(self.end_build(
            aspect, suite='stable', mirror='http://deb.example.com'))

        self.assertEqual(
            {'product': {'apt': {'img': {
                'suite': 'stable', 'mirror': 'http://deb.example.com'}}}},
            aspect.env.env['__Csversion__'])
        self.assertEqual(1, len(aspect.log.called('passed')))

    def test_end_build_records_a_copy_of_any_mapping(self):
        aspect = self.aspect()
        options = types.MappingProxyType({'suite': 'stable'})

        aspect.end__build('build', {'tag': 'img'}, None, options)

        recorded = aspect.env.env['__Csversion__']['product']['apt']['img']
        self.assertIs(dict, type(recorded))
        self.assertEqual({'suite': 'stable'}, recorded)

    def test_end_build_keeps_what_is_already_recorded(self):
        aspect = self.aspect()
        aspect.env.env['__Csversion__'] = {
            'sources': {'bash': {}},
            'product': {'build': {'img': {'BUILD': '1'}}}}

        self.end_build(aspect, suite='stable')

        csversion = aspect.env.env['__Csversion__']
        self.assertEqual({'bash': {}}, csversion['sources'])
        self.assertEqual({'img': {'BUILD': '1'}}, csversion['product']['build'])
        self.assertEqual({'img': {'suite': 'stable'}}, csversion['product']['apt'])

    def test_end_build_keeps_each_tag_separately(self):
        aspect = self.aspect()

        self.end_build(aspect, tag='one', suite='stable')
        self.end_build(aspect, tag='two', suite='testing')

        self.assertEqual(
            {'one': {'suite': 'stable'}, 'two': {'suite': 'testing'}},
            aspect.env.env['__Csversion__']['product']['apt'])
        self.assertEqual([], aspect.log.called('warning'))

    def test_end_build_same_tag_twice_warns_and_overwrites(self):
        aspect = self.aspect()
        self.end_build(aspect, suite='stable')

        self.end_build(aspect, suite='testing')

        self.assertEqual(
            {'img': {'suite': 'testing'}},
            aspect.env.env['__Csversion__']['product']['apt'])
        self.assertEqual(1, len(aspect.log.called('warning')))


if __name__ == '__main__':
    unittest.main()
