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
"""Git URL handling: urlparse.urlparse -> urllib.parse.urlparse.

CsversionRecordGit turns the URL a GitDependent section pulled into the
repo key of __Csversion__; CsversionRecordThisGit does the same for the
remote of a repo on disk.  The second uses a real temporary git repository
(and so needs the git executable and GitPython; it skips without them).
"""
import os
import shutil
import subprocess
import types
import unittest

from . import helpers


class TestCsversionRecordGit(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.module = helpers.import_plugin('CsversionRecordGit')

    def recorder(self):
        return helpers.make_module(self.module.CsversionRecordGit)

    @staticmethod
    def pulled(sha):
        """What GitDependent reports: ((result, sha), code, message)."""
        return types.SimpleNamespace(
            _getReturnValue=lambda phase: (('checkout', sha), 0, 'ok'))

    def test_url_path_becomes_the_repo_key(self):
        for url, repo in [
                ('https://git.example.com/org/project.git', 'org/project.git'),
                ('ssh://git@git.example.com:2222/team/sub/proj', 'team/sub/proj'),
                ('git://git.example.com/top.git', 'top.git')]:
            with self.subTest(url=url):
                recorder = self.recorder()

                self.assertTrue(recorder.passed__sources(
                    'sources', {'tag': 'img'}, self.pulled('abc123'),
                    {'URL': url, 'ref': 'refs/heads/dev:master'}))

                self.assertEqual(
                    {repo: {'img': ('git', {
                        'BRANCH': 'master', 'REF': 'abc123', 'URL': url})}},
                    recorder.env.env['__Csversion__']['sources'])

    def test_a_failed_pull_is_reported_not_recorded(self):
        recorder = self.recorder()
        failed = types.SimpleNamespace(
            _getReturnValue=lambda phase: (None, 'ERR', 'clone failed'))

        self.assertFalse(recorder.passed__pull(
            'pull', {'tag': 'img'}, failed,
            {'URL': 'https://git.example.com/org/project.git', 'ref': 'm'}))

        self.assertEqual(1, len(recorder.log.called('failed')))
        self.assertEqual({}, recorder.env.env['__Csversion__']['sources'])


class TestCsversionRecordThisGit(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if shutil.which('git') is None:
            raise unittest.SkipTest("git executable not found")
        cls.module = helpers.import_plugin('CsversionRecordThisGit')

    def setUp(self):
        self.workdir = helpers.make_tempdir(self)
        self.repo = os.path.join(self.workdir, 'checkout')
        os.makedirs(self.repo)
        self.git_env = dict(
            os.environ,
            HOME=self.workdir,
            GIT_CONFIG_NOSYSTEM='1',
            GIT_CONFIG_GLOBAL=os.devnull,
            GIT_AUTHOR_NAME='Test', GIT_AUTHOR_EMAIL='test@example.com',
            GIT_COMMITTER_NAME='Test', GIT_COMMITTER_EMAIL='test@example.com')
        self.git('init', '-q')
        self.git('symbolic-ref', 'HEAD', 'refs/heads/main')
        self.git('-c', 'commit.gpgsign=false',
                 'commit', '-q', '--allow-empty', '-m', 'first')
        self.sha = self.git('rev-parse', 'HEAD').strip()

    def git(self, *args):
        return subprocess.check_output(
            ['git', '-C', self.repo] + list(args),
            env=self.git_env, universal_newlines=True)

    def recorder(self):
        return helpers.make_module(self.module.CsversionRecordThisGit)

    def test_tracked_remote_url_path_becomes_the_repo_key(self):
        self.git('remote', 'add', 'origin', 'https://placeholder.invalid/x')
        self.git('update-ref', 'refs/remotes/origin/main', 'HEAD')
        self.git('config', 'branch.main.remote', 'origin')
        self.git('config', 'branch.main.merge', 'refs/heads/main')
        for url, repo in [
                ('https://git.example.com/team/proj.git', 'team/proj.git'),
                ('ssh://git@git.example.com:2222/team/proj.git',
                 'team/proj.git')]:
            with self.subTest(url=url):
                self.git('remote', 'set-url', 'origin', url)
                recorder = self.recorder()

                self.assertTrue(recorder.pull(
                    {'tag': 'img', 'repopath': self.repo}))

                self.assertEqual(
                    {repo: {'img': ('git', {
                        'BRANCH': 'main', 'REF': self.sha, 'URL': url})}},
                    recorder.env.env['__Csversion__']['sources'])

    def test_repo_without_a_remote_is_recorded_as_local(self):
        recorder = self.recorder()

        self.assertTrue(recorder.pull({'tag': 'img', 'repopath': self.repo}))

        self.assertEqual(
            {'checkout': {'img': ('git', {
                'BRANCH': '(local) main', 'REF': self.sha,
                'URL': '(local) checkout'})}},
            recorder.env.env['__Csversion__']['sources'])


if __name__ == '__main__':
    unittest.main()
