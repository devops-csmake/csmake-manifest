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
"""CsversionRecordGit turns the URL a GitDependent section pulled into the
repo key of __Csversion__ (urlparse.urlparse -> urllib.parse.urlparse).
The GitDependent section it observes is replaced by a scripted fake."""
import types
import unittest

from . import helpers

URL = 'https://git.example.com/org/project.git'


def pulled(sha):
    """What GitDependent._getReturnValue reports on success."""
    return types.SimpleNamespace(
        _getReturnValue=lambda phase: (('checkout', sha), 0, 'ok'))


def failed(result=None):
    return types.SimpleNamespace(
        _getReturnValue=lambda phase: (result, 'ERR', 'clone failed'))


class TestCsversionRecordGit(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.module = helpers.import_plugin('CsversionRecordGit')

    def recorder(self):
        return helpers.make_module(self.module.CsversionRecordGit)

    def sources(self, recorder):
        return recorder.env.env['__Csversion__']['sources']

    def test_passed_pull_uses_the_url_path_as_the_repo_key(self):
        for url, repo in [
                (URL, 'org/project.git'),
                ('ssh://git@git.example.com:2222/team/sub/proj',
                 'team/sub/proj'),
                ('git://git.example.com/top.git', 'top.git'),
                ('file:///srv/git/local.git', 'srv/git/local.git')]:
            with self.subTest(url=url):
                recorder = self.recorder()

                self.assertTrue(recorder.passed__pull(
                    'pull', {'tag': 'img'}, pulled('abc123'),
                    {'URL': url, 'ref': 'master'}))

                self.assertEqual(
                    {repo: {'img': ('git', {
                        'BRANCH': 'master', 'REF': 'abc123', 'URL': url})}},
                    self.sources(recorder))
                self.assertEqual(1, len(recorder.log.called('passed')))

    def test_passed_pull_records_the_last_part_of_the_ref_as_branch(self):
        recorder = self.recorder()

        recorder.passed__pull(
            'pull', {'tag': 'img'}, pulled('abc123'),
            {'URL': URL, 'ref': 'refs/heads/dev:master'})

        self.assertEqual(
            'master',
            self.sources(recorder)['org/project.git']['img'][1]['BRANCH'])

    def test_passed_sources_records_the_same_as_passed_pull(self):
        recorder = self.recorder()

        self.assertTrue(recorder.passed__sources(
            'sources', {'tag': 'img'}, pulled('abc123'),
            {'URL': URL, 'ref': 'master'}))

        self.assertEqual(
            ('git', {'BRANCH': 'master', 'REF': 'abc123', 'URL': URL}),
            self.sources(recorder)['org/project.git']['img'])

    def test_passed_pull_keeps_every_tag_of_the_same_repo(self):
        recorder = self.recorder()
        gitoptions = {'URL': URL, 'ref': 'master'}

        recorder.passed__pull(
            'pull', {'tag': 'one'}, pulled('111'), gitoptions)
        recorder.passed__pull(
            'pull', {'tag': 'two'}, pulled('222'), gitoptions)

        tags = self.sources(recorder)['org/project.git']
        self.assertEqual(
            {'one': '111', 'two': '222'},
            dict((tag, entry[1]['REF']) for tag, entry in tags.items()))
        self.assertEqual([], recorder.log.called('warning'))

    def test_passed_pull_same_repo_and_tag_warns_and_overwrites(self):
        recorder = self.recorder()
        gitoptions = {'URL': URL, 'ref': 'master'}
        recorder.passed__pull(
            'pull', {'tag': 'img'}, pulled('111'), gitoptions)

        recorder.passed__pull(
            'pull', {'tag': 'img'}, pulled('222'), gitoptions)

        self.assertEqual(
            '222', self.sources(recorder)['org/project.git']['img'][1]['REF'])
        self.assertEqual(1, len(recorder.log.called('warning')))

    def test_passed_pull_adds_sources_to_an_existing_csversion(self):
        recorder = self.recorder()
        recorder.env.env['__Csversion__'] = {'product': {'build': {}}}

        recorder.passed__pull(
            'pull', {'tag': 'img'}, pulled('abc'), {'URL': URL, 'ref': 'm'})

        self.assertEqual({'product', 'sources'},
                         set(recorder.env.env['__Csversion__']))

    def test_passed_pull_with_no_result_is_reported_not_recorded(self):
        recorder = self.recorder()

        self.assertFalse(recorder.passed__pull(
            'pull', {'tag': 'img'}, failed(None),
            {'URL': URL, 'ref': 'master'}))

        self.assertEqual(1, len(recorder.log.called('failed')))
        self.assertEqual({}, self.sources(recorder))

    def test_passed_pull_with_an_empty_result_is_reported_not_recorded(self):
        recorder = self.recorder()

        self.assertFalse(recorder.passed__pull(
            'pull', {'tag': 'img'}, failed(()), {'URL': URL, 'ref': 'm'}))

        self.assertEqual({}, self.sources(recorder))


if __name__ == '__main__':
    unittest.main()
