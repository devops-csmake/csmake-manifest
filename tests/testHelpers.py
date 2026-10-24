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
"""The fakes are only worth having if they keep the real API's type contract;
these tests pin that down, so a fake that quietly returned str regardless of
arguments could not let a missing universal_newlines slip through."""
import subprocess
import unittest

from . import csmake_alias, helpers
from .helpers import FakePopen, popen_result

PIPES = {'stdout': subprocess.PIPE, 'stderr': subprocess.PIPE}


class TestFakePopen(unittest.TestCase):

    def communicate(self, result, **kwargs):
        popen = FakePopen(result)
        process = popen(['cmd'], **dict(PIPES, **kwargs))
        return process, process.communicate()

    def test_output_is_bytes_unless_text_was_requested(self):
        _, (out, err) = self.communicate(popen_result('out\n', 'err\n'))

        self.assertEqual((b'out\n', b'err\n'), (out, err))

    def test_output_is_str_for_each_way_of_asking_for_text(self):
        for kwargs in [{'universal_newlines': True}, {'text': True},
                       {'encoding': 'utf-8'}, {'errors': 'strict'}]:
            with self.subTest(**kwargs):
                _, (out, err) = self.communicate(
                    popen_result('out\n', 'err\n'), **kwargs)

                self.assertEqual(('out\n', 'err\n'), (out, err))

    def test_text_output_has_universal_newlines_and_bytes_are_decoded(self):
        _, (out, _) = self.communicate(
            popen_result(u'a\r\nb\rc é\n'.encode('utf-8')),
            universal_newlines=True)

        self.assertEqual(u'a\nb\nc é\n', out)

    def test_bytes_output_is_left_alone_without_text(self):
        _, (out, _) = self.communicate(popen_result(b'a\r\n\xff'))

        self.assertEqual(b'a\r\n\xff', out)

    def test_a_stream_that_was_not_piped_is_none(self):
        process = FakePopen(popen_result('out', 'err'))(
            ['cmd'], stdout=subprocess.PIPE)

        self.assertEqual((b'out', None), process.communicate())

    def test_returncode_is_none_until_communicate_has_run(self):
        process, _ = self.communicate(popen_result('', '', 3))
        fresh = FakePopen(popen_result('', '', 3))(['cmd'], **PIPES)

        self.assertIsNone(fresh.returncode)
        fresh.communicate()
        self.assertEqual(3, fresh.returncode)
        self.assertEqual(3, process.returncode)

    def test_calls_are_recorded_with_their_arguments(self):
        popen = FakePopen(popen_result(), popen_result())

        popen(['a', 'b'], shell=False, **PIPES)
        popen('c d', shell=True, **PIPES)

        self.assertEqual(
            [(['a', 'b'], dict(PIPES, shell=False)),
             ('c d', dict(PIPES, shell=True))], popen.calls)

    def test_an_unscripted_call_fails_the_test(self):
        with self.assertRaises(AssertionError):
            FakePopen()(['cmd'], **PIPES)

    def test_a_scripted_exception_is_raised_by_the_call(self):
        with self.assertRaises(OSError):
            FakePopen(OSError('sudo: not found'))(['sudo'], **PIPES)


class TestCsmakeAlias(unittest.TestCase):

    def test_csmake_modules_are_the_same_objects_as_csmakecore_modules(self):
        csmake_alias.install()
        import importlib
        aliased = importlib.import_module('Csmake.CsmakeModule')
        core = importlib.import_module('CsmakeCore.CsmakeModule')

        self.assertIs(core, aliased)
        self.assertIs(core.CsmakeModule, aliased.CsmakeModule)

    def test_import_plugin_reports_a_missing_plugin_as_an_error_not_a_skip(self):
        with self.assertRaises(ImportError):
            helpers.import_plugin('NoSuchPluginModule')


if __name__ == '__main__':
    unittest.main()
