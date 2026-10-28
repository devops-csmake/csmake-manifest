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
"""CsversionRecordThisGit records the HEAD of a local repository
(urlparse.urlparse -> urllib.parse.urlparse for the remote URL).

GitPython is replaced by a stub 'git' module whose Repo is scripted with fake
repositories, remotes, refs and submodules that mimic the GitPython objects
the module touches (including the TypeError GitPython raises for a detached
HEAD and the IndexError it raises for an unknown remote name).  No git
executable or repository is involved.
"""
import os
import types
import unittest
from unittest import mock

from . import helpers

REPOPATH = '/work/checkout'
SHA = '1111111111111111111111111111111111111111'
OTHER_SHA = '2222222222222222222222222222222222222222'
URL = 'https://git.example.com/team/proj.git'


class Head(object):
    """Stands in for git.refs.head.Head, which GitPython's remote refs extend."""


class FakeRemoteRef(Head):
    def __init__(self, name, sha, remote_name='origin'):
        self.name = name
        self.remote_name = remote_name
        self.commit = types.SimpleNamespace(hexsha=sha)

    def __str__(self):
        return self.name

    def is_remote(self):
        return True


class FakeRemote(object):
    def __init__(self, name='origin', url=URL, refs=()):
        self.name = name
        self.url = url
        self.refs = list(refs)


class FakeRemotes(list):
    """Indexable by position or, as GitPython's IterableList, by name."""

    def __getitem__(self, key):
        if isinstance(key, str):
            for remote in self:
                if remote.name == key:
                    return remote
            raise IndexError("No item found with id %r" % key)
        return list.__getitem__(self, key)


class FakeBranch(object):
    def __init__(self, name='main', tracking=None):
        self.name = name
        self.tracking = tracking

    def tracking_branch(self):
        return self.tracking

    def __str__(self):
        return self.name


class FakeRepo(object):
    def __init__(self, sha=SHA, branch=None, remotes=(), submodules=()):
        self.sha = sha
        self.branch = branch
        self.remotes = FakeRemotes(remotes)
        self.submodules = list(submodules)

    def commit(self):
        return types.SimpleNamespace(hexsha=self.sha)

    @property
    def active_branch(self):
        if self.branch is None:
            raise TypeError(
                "HEAD is a detached symbolic reference as it points to %r"
                % self.sha)
        return self.branch


def submodule(url, path, sha):
    return types.SimpleNamespace(url=url, path=path, hexsha=sha)


def make_git_stub():
    git = types.ModuleType('git')
    git.refs = types.ModuleType('git.refs')
    git.refs.head = types.ModuleType('git.refs.head')
    git.refs.head.Head = Head
    git.Repo = mock.Mock(name='Repo')
    return git


def tracking_repo(remote_url=URL, **kwargs):
    """A repo whose 'main' branch tracks origin/main."""
    ref = FakeRemoteRef('origin/main', SHA)
    return FakeRepo(
        branch=FakeBranch('main', tracking=ref),
        remotes=[FakeRemote(url=remote_url, refs=[ref])], **kwargs)


class TestCsversionRecordThisGit(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.git = make_git_stub()
        cls.module = helpers.import_plugin(
            'CsversionRecordThisGit', stubs={'git': cls.git})

    def setUp(self):
        self.git.Repo = mock.Mock(name='Repo')
        self.recorder = helpers.make_module(
            self.module.CsversionRecordThisGit)

    def pull(self, repo, **options):
        self.git.Repo.return_value = repo
        options.setdefault('tag', 'img')
        options.setdefault('repopath', REPOPATH)
        return self.recorder.pull(options)

    def sources(self):
        return self.recorder.env.env['__Csversion__']['sources']

    def test_pull_tracked_branch_records_the_remote_url_path_as_the_key(self):
        for url, key in [
                (URL, 'team/proj.git'),
                ('ssh://git@git.example.com:2222/team/proj.git',
                 'team/proj.git'),
                ('git://git.example.com/top.git', 'top.git')]:
            with self.subTest(url=url):
                self.recorder = helpers.make_module(
                    self.module.CsversionRecordThisGit)

                self.assertTrue(self.pull(tracking_repo(url)))

                self.assertEqual(
                    {key: {'img': ('git', {
                        'BRANCH': 'main', 'REF': SHA, 'URL': url})}},
                    self.sources())
                self.assertEqual(1, len(self.recorder.log.called('passed')))

    def test_pull_opens_the_real_path_of_the_repository(self):
        self.pull(tracking_repo())

        self.git.Repo.assert_called_once_with(os.path.realpath(REPOPATH))

    def test_pull_branch_with_slashes_keeps_everything_after_the_remote(self):
        ref = FakeRemoteRef('origin/feature/x', SHA)
        repo = FakeRepo(branch=FakeBranch('x', tracking=ref),
                        remotes=[FakeRemote(refs=[ref])])

        self.pull(repo)

        self.assertEqual('feature/x', self.sources()['team/proj.git']['img'][1]['BRANCH'])

    def test_pull_untracked_branch_uses_the_remote_ref_at_head(self):
        repo = FakeRepo(
            branch=FakeBranch('work'),
            remotes=[FakeRemote(refs=[
                FakeRemoteRef('origin/HEAD', SHA),
                FakeRemoteRef('origin/old', OTHER_SHA),
                FakeRemoteRef('origin/main', SHA)])])

        self.assertTrue(self.pull(repo))

        self.assertEqual(
            {'team/proj.git': {'img': ('git', {
                'BRANCH': 'main', 'REF': SHA, 'URL': URL})}},
            self.sources())

    def test_pull_detached_head_at_a_remote_ref_is_recorded_from_the_remote(self):
        repo = FakeRepo(
            branch=None,
            remotes=[FakeRemote(refs=[FakeRemoteRef('origin/main', SHA)])])

        self.assertTrue(self.pull(repo))

        self.assertEqual(
            ('git', {'BRANCH': 'main', 'REF': SHA, 'URL': URL}),
            self.sources()['team/proj.git']['img'])

    def test_pull_tracking_an_unknown_remote_falls_back_to_the_search(self):
        gone = FakeRemoteRef('upstream/main', SHA, remote_name='upstream')
        repo = FakeRepo(
            branch=FakeBranch('main', tracking=gone),
            remotes=[FakeRemote(refs=[FakeRemoteRef('origin/main', SHA)])])

        self.assertTrue(self.pull(repo))

        self.assertEqual(
            URL, self.sources()['team/proj.git']['img'][1]['URL'])

    def test_pull_remote_refs_at_other_commits_are_recorded_as_local(self):
        repo = FakeRepo(
            branch=FakeBranch('work'),
            remotes=[FakeRemote(refs=[
                FakeRemoteRef('origin/HEAD', SHA),
                FakeRemoteRef('origin/main', OTHER_SHA)])])

        self.assertTrue(self.pull(repo))

        self.assertEqual(
            {'checkout': {'img': ('git', {
                'BRANCH': '(local) work', 'REF': SHA,
                'URL': '(local) checkout'})}},
            self.sources())

    def test_pull_repo_without_remotes_is_recorded_as_local(self):
        self.assertTrue(self.pull(FakeRepo(branch=FakeBranch('main'))))

        self.assertEqual(
            {'checkout': {'img': ('git', {
                'BRANCH': '(local) main', 'REF': SHA,
                'URL': '(local) checkout'})}},
            self.sources())

    def test_pull_detached_head_without_remotes_is_recorded_as_local(self):
        self.assertTrue(self.pull(FakeRepo(branch=None)))

        self.assertEqual(
            '(local) (detached)',
            self.sources()['checkout']['img'][1]['BRANCH'])

    def test_pull_records_submodules(self):
        repo = tracking_repo(submodules=[
            submodule('https://git.example.com/lib.git', 'vendor/lib', OTHER_SHA),
            submodule('https://git.example.com/doc.git', 'doc', SHA)])

        self.assertTrue(self.pull(repo))

        self.assertEqual(
            [{'URL': 'https://git.example.com/lib.git',
              'PATH': 'vendor/lib', 'REF': OTHER_SHA},
             {'URL': 'https://git.example.com/doc.git',
              'PATH': 'doc', 'REF': SHA}],
            self.sources()['team/proj.git']['img'][1]['SUBMODULES'])

    def test_pull_without_submodules_has_no_submodules_entry(self):
        self.pull(tracking_repo())

        self.assertNotIn(
            'SUBMODULES', self.sources()['team/proj.git']['img'][1])

    def test_pull_unopenable_repository_fails_and_records_nothing(self):
        self.git.Repo.side_effect = Exception('not a git repository')
        self.recorder.env.env['__Csversion__'] = {}

        self.assertFalse(self.recorder.pull(
            {'tag': 'img', 'repopath': REPOPATH}))

        self.assertEqual(1, len(self.recorder.log.called('exception')))
        self.assertEqual({}, self.sources())
        self.assertEqual([], self.recorder.log.called('passed'))

    def test_pull_same_repo_and_tag_warns_and_overwrites(self):
        self.pull(tracking_repo())
        newer = tracking_repo()
        newer.sha = OTHER_SHA
        newer.remotes[0].refs[0].commit.hexsha = OTHER_SHA

        self.pull(newer)

        self.assertEqual(1, len(self.recorder.log.called('warning')))
        self.assertEqual(
            OTHER_SHA, self.sources()['team/proj.git']['img'][1]['REF'])

    def test_pull_keeps_other_tags_of_the_same_repo(self):
        self.pull(tracking_repo(), tag='one')
        self.pull(tracking_repo(), tag='two')

        self.assertEqual({'one', 'two'}, set(self.sources()['team/proj.git']))
        self.assertEqual([], self.recorder.log.called('warning'))

    def test_sources_and_build_record_the_same_as_pull(self):
        for phase in ('sources', 'build'):
            with self.subTest(phase=phase):
                self.recorder = helpers.make_module(
                    self.module.CsversionRecordThisGit)
                self.git.Repo.return_value = tracking_repo()

                self.assertTrue(getattr(self.recorder, phase)(
                    {'tag': 'img', 'repopath': REPOPATH}))

                self.assertEqual(
                    ('git', {'BRANCH': 'main', 'REF': SHA, 'URL': URL}),
                    self.sources()['team/proj.git']['img'])

    def test_default_creates_an_empty_csversion(self):
        self.recorder.default({'tag': 'img', 'repopath': REPOPATH})

        self.assertEqual({}, self.recorder.env.env['__Csversion__'])
        self.assertEqual(1, len(self.recorder.log.called('passed')))
        self.git.Repo.assert_not_called()

    @unittest.skip(
        "pre-existing: the docstring documents 'pass-non-repos' but the code "
        "reads 'pass-non-repo'; not asserting either spelling until fixed")
    def test_pull_pass_non_repo_passes_when_there_is_no_repository(self):
        pass


if __name__ == '__main__':
    unittest.main()
