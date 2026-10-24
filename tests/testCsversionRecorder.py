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
"""CsversionRecorder pickles __Csversion__ between phases and builds.

The py3 hazards are the pickle file modes (must be binary) and the
iteritems() -> items() conversion in the merge.  These tests use real files
and the real pickle module.
"""
import os
import pickle
import unittest

from . import helpers


def git_entry(ref):
    return ('git', {'BRANCH': 'master', 'REF': ref})


class TestCsversionRecorder(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.module = helpers.import_plugin('CsversionRecorder')

    def make_recorder(self, csversion=None):
        recorder = helpers.make_module(self.module.CsversionRecorder)
        if csversion is not None:
            recorder.env.env['__Csversion__'] = csversion
        return recorder

    def test_default_writes_binary_pickle_that_loads_back(self):
        workdir = helpers.make_tempdir(self)
        record = os.path.join(workdir, 'nested', 'csversion.pickle')
        state = {'sources': {'org/repo': {'img': git_entry('abc123')}}}

        result = self.make_recorder(state).default({'file': record})

        self.assertEqual(state, result)
        with open(record, 'rb') as f:
            self.assertEqual(state, pickle.load(f))

    def test_merge_order_other_records_then_file_then_env(self):
        workdir = helpers.make_tempdir(self)
        first = os.path.join(workdir, 'first.pickle')
        second = os.path.join(workdir, 'second.pickle')
        record = os.path.join(workdir, 'record.pickle')
        missing = os.path.join(workdir, 'never-written.pickle')
        for path, state in [
                (first, {'sources': {'org/repo': {
                    'a': git_entry('first'), 'b': git_entry('first')}}}),
                (second, {'sources': {'org/repo': {
                    'b': git_entry('second'), 'c': git_entry('second')}}}),
                (record, {'sources': {'org/repo': {
                    'c': git_entry('record'), 'd': git_entry('record')}},
                    'product': {'build': {'img': {'BUILD': '1'}}}})]:
            with open(path, 'wb') as f:
                pickle.dump(state, f)
        env_state = {'sources': {
            'org/repo': {'d': git_entry('env')},
            'org/other': {'a': git_entry('env')}}}
        # newline and comma delimited, with a file that does not exist
        other_records = '%s\n%s,%s' % (first, missing, second)

        result = self.make_recorder(env_state).default(
            {'file': record, 'other-records': other_records})

        self.assertEqual(
            {'a': git_entry('first'),      # only in first
             'b': git_entry('second'),     # second updates first
             'c': git_entry('record'),     # file updates other-records
             'd': git_entry('env')},       # __Csversion__ updates last
            result['sources']['org/repo'])
        self.assertEqual({'a': git_entry('env')}, result['sources']['org/other'])
        self.assertEqual({'build': {'img': {'BUILD': '1'}}}, result['product'])
        # and what was stashed is exactly what was returned
        with open(record, 'rb') as f:
            self.assertEqual(result, pickle.load(f))

    def test_clean_removes_file_and_directory_it_created(self):
        workdir = helpers.make_tempdir(self)
        record = os.path.join(workdir, 'made-by-recorder', 'csversion.pickle')
        recorder = self.make_recorder({'sources': {}})
        recorder.default({'file': record})
        self.assertTrue(os.path.exists(record))

        self.assertTrue(recorder.clean({'file': record}))

        self.assertFalse(os.path.exists(record))
        self.assertFalse(os.path.exists(os.path.dirname(record)))


if __name__ == '__main__':
    unittest.main()
