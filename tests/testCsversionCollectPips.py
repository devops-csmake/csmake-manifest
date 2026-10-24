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
"""CsversionCollectPips parses 'pip list' output, global and per virtualenv.

It makes three kinds of Popen call, in this order: a shell pipeline that
finds virtualenvs ('find . | grep bin/activate_this'), 'pip list' for the
global environment, and one 'source <venv>/bin/activate; pip list' shell
script per virtualenv.  Each needs text output (universal_newlines) to be
split and matched under Python 3.  subprocess.Popen is replaced by
helpers.FakePopen, which returns bytes unless the module asks for text.
"""
import unittest

from . import helpers
from .helpers import popen_result

CHROOT = '/mnt/chroot'
DELIM = '=-=-=-=-=-=-=-=-='
FIND_VENVS = 'sudo -E chroot %s find . | grep "bin/activate_this"' % CHROOT


def pip(venv, package, version):
    return ('pip', {'VENV': venv, 'PACKAGE': package, 'VERSION': version})


class TestCsversionCollectPips(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.module = helpers.import_plugin('CsversionCollectPips')

    def build(self, *results):
        collector = helpers.make_module(self.module.CsversionCollectPips)
        popen = helpers.patch_popen(self, self.module, *results)
        result = collector.build({'tag': 'img', 'chroot': CHROOT})
        return collector, popen, result

    def test_build_parses_the_global_pip_list(self):
        collector, _, result = self.build(
            popen_result('', '', 1),
            popen_result('pip (9.0.1)\nsetuptools (36.0.1)\n'))

        self.assertEqual({
            'pip': {'img___global': pip('__global', 'pip', '9.0.1')},
            'setuptools': {
                'img___global': pip('__global', 'setuptools', '36.0.1')}},
            result)
        self.assertIs(result, collector.env.env['__Csversion__']['sources'])
        self.assertEqual(1, len(collector.log.called('passed')))

    def test_build_makes_its_calls_in_order_with_the_expected_commands(self):
        _, popen, _ = self.build(
            popen_result('./opt/venvA/bin/activate_this.py\n'),
            popen_result('pip (9.0.1)\n'),
            popen_result(DELIM + '\nFlask (0.12.2)\n'))

        self.assertEqual(3, len(popen.calls))
        (find_args, find_kwargs), (global_args, global_kwargs), \
            (venv_args, venv_kwargs) = popen.calls
        self.assertEqual(FIND_VENVS, find_args)
        self.assertTrue(find_kwargs['shell'])
        self.assertEqual(
            ['sudo', '-E', 'chroot', CHROOT, 'pip', 'list'], global_args)
        self.assertFalse(global_kwargs.get('shell'))
        self.assertTrue(venv_kwargs['shell'])
        self.assertIn('sudo -E chroot %s /bin/bash -c' % CHROOT, venv_args)
        self.assertIn('source /opt/venvA/bin/activate;', venv_args)
        self.assertIn('echo %s;' % DELIM, venv_args)
        self.assertIn('pip list;', venv_args)

    def test_build_lists_each_virtualenv_separately_from_the_global_one(self):
        _, _, result = self.build(
            popen_result('./opt/venvA/bin/activate_this.py\n'
                         './srv/app/venvB/bin/activate_this.py\n\n'),
            popen_result('pip (9.0.1)\n'),
            popen_result('activating...\n' + DELIM + '\n'
                         'Flask (0.12.2)\npip (9.0.3)\n'),
            popen_result(DELIM + '\nrequests (2.18.4)\n'))

        self.assertEqual({
            'pip': {'img___global': pip('__global', 'pip', '9.0.1'),
                    'img_/opt/venvA': pip('/opt/venvA', 'pip', '9.0.3')},
            'Flask': {'img_/opt/venvA': pip('/opt/venvA', 'Flask', '0.12.2')},
            'requests': {'img_/srv/app/venvB': pip(
                '/srv/app/venvB', 'requests', '2.18.4')}},
            result)

    def test_build_without_virtualenvs_makes_no_per_venv_calls(self):
        collector, popen, _ = self.build(
            popen_result('', 'grep: no match\n', 1),
            popen_result('pip (9.0.1)\n'))

        self.assertEqual(2, len(popen.calls))
        self.assertEqual(
            [("Search for virtual environments failed",)],
            collector.log.called('info')[:1])

    def test_build_skips_a_virtualenv_whose_pip_list_fails(self):
        collector, popen, result = self.build(
            popen_result('./opt/venvA/bin/activate_this.py\n'
                         './opt/venvB/bin/activate_this.py\n'),
            popen_result('pip (9.0.1)\n'),
            popen_result('', 'activate: no such file\n', 1),
            popen_result(DELIM + '\nrequests (2.18.4)\n'))

        self.assertEqual(4, len(popen.calls))
        self.assertEqual(
            {'pip', 'requests'}, set(result))
        self.assertEqual(
            {'img_/opt/venvB': pip('/opt/venvB', 'requests', '2.18.4')},
            result['requests'])
        self.assertIn(
            ("Could not get information on %s", '/opt/venvA'),
            collector.log.called('info'))

    def test_build_logs_and_skips_lines_it_cannot_parse(self):
        collector, _, result = self.build(
            popen_result('', '', 1),
            popen_result('pip (9.0.1)\n'
                         '\n'
                         'You are using pip version 9.0.1, however 9.0.3 is available.\n'
                         'Package    Version\n'))

        self.assertEqual({'pip'}, set(result))
        self.assertEqual(
            [("%s was not recognized from pip list",
              'You are using pip version 9.0.1, however 9.0.3 is available.'),
             ("%s was not recognized from pip list", 'Package    Version')],
            [args for args in collector.log.called('info')
             if 'not recognized' in args[0]])

    def test_build_with_empty_pip_list_records_nothing(self):
        _, _, result = self.build(popen_result('', '', 1), popen_result(''))

        self.assertEqual({}, result)

    def test_build_decodes_non_ascii_package_names(self):
        _, _, result = self.build(
            popen_result('', '', 1),
            popen_result(u'café (1.0)\n'.encode('utf-8')))

        self.assertEqual({u'café'}, set(result))

    def test_build_same_package_listed_twice_warns_and_keeps_the_last(self):
        collector, _, result = self.build(
            popen_result('', '', 1),
            popen_result('pip (9.0.1)\npip (9.0.3)\n'))

        self.assertEqual(
            {'img___global': pip('__global', 'pip', '9.0.3')}, result['pip'])
        self.assertEqual(1, len(collector.log.called('warning')))


if __name__ == '__main__':
    unittest.main()
