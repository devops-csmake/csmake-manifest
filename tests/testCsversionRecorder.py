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
iteritems() -> items() conversion in the merge.  The file mode is the
behaviour under test, so these use real files in a temp dir and the real
pickle module.
"""
import os
import pickle
import unittest

from . import helpers


def git_entry(ref):
    return ('git', {'BRANCH': 'master', 'REF': ref})


def dump(path, state):
    with open(path, 'wb') as f:
        pickle.dump(state, f)


def load(path):
    with open(path, 'rb') as f:
        return pickle.load(f)


class TestCsversionRecorder(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.module = helpers.import_plugin('CsversionRecorder')

    def setUp(self):
        self.workdir = helpers.make_tempdir(self)

    def path(self, *parts):
        return os.path.join(self.workdir, *parts)

    def recorder(self, csversion=None):
        recorder = helpers.make_module(self.module.CsversionRecorder)
        if csversion is not None:
            recorder.env.env['__Csversion__'] = csversion
        return recorder

    def test_default_writes_a_binary_pickle_that_loads_back(self):
        record = self.path('nested', 'csversion.pickle')
        state = {'sources': {'org/repo': {'img': git_entry('abc123')}}}
        recorder = self.recorder(state)

        result = recorder.default({'file': record})

        self.assertEqual(state, result)
        self.assertEqual(state, load(record))
        self.assertEqual(state, recorder.env.env['__Csversion__'])
        self.assertEqual(1, len(recorder.log.called('passed')))

    def test_default_without_state_in_the_environment_stashes_an_empty_record(self):
        record = self.path('csversion.pickle')
        recorder = self.recorder()

        result = recorder.default({'file': record})

        self.assertEqual({}, result)
        self.assertEqual({}, load(record))
        self.assertEqual(
            [("No current __Csversion__ exists",)],
            recorder.log.called('info'))

    def test_default_merges_other_records_then_file_then_environment(self):
        first, second = self.path('first.pickle'), self.path('second.pickle')
        record = self.path('record.pickle')
        dump(first, {'sources': {'org/repo': {
            'a': git_entry('first'), 'b': git_entry('first')}}})
        dump(second, {'sources': {'org/repo': {
            'b': git_entry('second'), 'c': git_entry('second')}}})
        dump(record, {
            'sources': {'org/repo': {
                'c': git_entry('record'), 'd': git_entry('record')}},
            'product': {'build': {'img': {'BUILD': '1'}}}})
        env_state = {'sources': {
            'org/repo': {'d': git_entry('env')},
            'org/other': {'a': git_entry('env')}}}

        result = self.recorder(env_state).default({
            'file': record, 'other-records': '%s\n%s' % (first, second)})

        self.assertEqual(
            {'a': git_entry('first'),      # only in first
             'b': git_entry('second'),     # second updates first
             'c': git_entry('record'),     # file updates other-records
             'd': git_entry('env')},       # __Csversion__ updates last
            result['sources']['org/repo'])
        self.assertEqual({'a': git_entry('env')}, result['sources']['org/other'])
        self.assertEqual({'build': {'img': {'BUILD': '1'}}}, result['product'])
        self.assertEqual(result, load(record))

    def test_default_other_records_may_be_comma_separated_and_missing(self):
        first, second = self.path('first.pickle'), self.path('second.pickle')
        dump(first, {'sources': {'x': {'a': git_entry('first')}}})
        dump(second, {'sources': {'y': {'a': git_entry('second')}}})
        listed = ' %s , %s,%s' % (first, self.path('never-written'), second)

        result = self.recorder().default({
            'file': self.path('record.pickle'), 'other-records': listed})

        self.assertEqual({'x', 'y'}, set(result['sources']))

    def test_default_empty_other_records_option_is_ignored(self):
        result = self.recorder({'sources': {}}).default({
            'file': self.path('record.pickle'), 'other-records': ''})

        self.assertEqual({'sources': {}}, result)

    def test_default_carries_state_over_from_the_file_of_an_earlier_run(self):
        options = {'file': self.path('csversion.pickle')}
        self.recorder({'sources': {'org/repo': {'img': git_entry('one')}}}
                      ).default(options)

        later = self.recorder().default(options)

        self.assertEqual(
            {'sources': {'org/repo': {'img': git_entry('one')}}}, later)

    def test_default_reads_a_pickle_written_by_python_2(self):
        record = self.path('csversion.pickle')
        # pickle protocol 0 as Python 2 wrote it, with STRING opcodes:
        # {'sources': {'org/repo': {'img': ('git', {'REF': 'abc'})}}}
        py2_pickle = (b"(dS'sources'\n(dS'org/repo'\n(dS'img'\n(S'git'\n"
                      b"(dS'REF'\nS'abc'\nstsss.")
        with open(record, 'wb') as f:
            f.write(py2_pickle)

        result = self.recorder().default({'file': record})

        self.assertEqual(
            {'sources': {'org/repo': {'img': ('git', {'REF': 'abc'})}}},
            result)

    def test_clean_removes_the_file_and_the_directory_it_created(self):
        record = self.path('made-by-recorder', 'csversion.pickle')
        recorder = self.recorder({'sources': {}})
        recorder.default({'file': record})
        self.assertTrue(os.path.exists(record))

        self.assertTrue(recorder.clean({'file': record}))

        self.assertFalse(os.path.exists(record))
        self.assertFalse(os.path.exists(os.path.dirname(record)))
        self.assertEqual(2, len(recorder.log.called('passed')))

    def test_clean_without_a_file_still_passes(self):
        recorder = self.recorder()

        self.assertTrue(recorder.clean({'file': self.path('absent.pickle')}))

    def test_clean_results_and_clean_build_clean_the_same_file(self):
        for phase in ('clean_results', 'clean_build'):
            with self.subTest(phase=phase):
                record = self.path(phase, 'csversion.pickle')
                recorder = self.recorder({'sources': {}})
                recorder.default({'file': record})

                self.assertTrue(getattr(recorder, phase)({'file': record}))

                self.assertFalse(os.path.exists(record))


if __name__ == '__main__':
    unittest.main()
