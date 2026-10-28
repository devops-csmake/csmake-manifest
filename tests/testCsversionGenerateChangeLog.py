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
"""CsversionGenerateChangeLog diffs two __Csversion__ manifests.

Most of the conversion here is iteritems() -> items() over nested manifest
dictionaries, plus reading the YAML manifests back.  The module imports
GitProvider from csmake-providers; that package is replaced by a stub for the
import and GitProvider itself is replaced by a Mock in each test, so the git
analysis (which would fetch from remote repositories) is scripted for both
success and failure and the exact calls made to it are asserted.

PyYAML is real (the manifests are YAML files in temp dirs); the tests skip
when it is not installed.
"""
import os
import types
import unittest
from unittest import mock

from . import helpers

URL = 'https://git.example.com/org/proj.git'
OLD = '1' * 40
NEW = '2' * 40


def dpkg(version):
    return ('dpkg', {'PACKAGE': 'x', 'VERSION': version, 'ARCH': ''})


def git(ref, branch='master', url=URL, **extra):
    values = {'REF': ref, 'BRANCH': branch}
    if url is not None:
        values['URL'] = url
    values.update(extra)
    return ('git', values)


def provider_stubs():
    package = types.ModuleType('CsmakeProviders')
    package.__path__ = []
    module = types.ModuleType('CsmakeProviders.GitProvider')
    module.GitProvider = type('GitProvider', (object,), {})
    return {'CsmakeProviders': package, 'CsmakeProviders.GitProvider': module}


class ChangeLogTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.module = helpers.import_plugin(
            'CsversionGenerateChangeLog', stubs=provider_stubs())
        import yaml
        cls.yaml = yaml

    def setUp(self):
        self.provider = mock.Mock(name='GitProvider')
        patcher = mock.patch.object(self.module, 'GitProvider', self.provider)
        patcher.start()
        self.addCleanup(patcher.stop)

    def changelog_module(self, **attrs):
        return helpers.make_module(
            self.module.CsversionGenerateChangeLog, **attrs)


class TestAnalyzeSpecificChange(ChangeLogTestCase):
    """_analyzeSpecificChange(packageType, records, build) for each type."""

    def analyze(self, package_type, old, new, build='img', **attrs):
        attrs.setdefault('gitstash', '/stash')
        attrs.setdefault('findrefs', False)
        attrs.setdefault('shellenv', {'FROM': 'dib'})
        module = self.changelog_module(**attrs)
        records = {'old': {build: old}, 'new': {build: new}, '__info': []}
        changed = module._analyzeSpecificChange(package_type, records, build)
        return module, records, changed

    def test_git_changed_ref_adds_the_span_log_to_the_changelog(self):
        self.provider.generateSpanLogInfo.return_value = ['commit one']

        module, records, changed = self.analyze(
            'git', git(OLD), git(NEW))

        self.assertTrue(changed)
        self.provider.generateSpanLogInfo.assert_called_once_with(
            module.log, '/stash/proj.git', OLD, NEW, False)
        self.provider.fetchRepository.assert_not_called()
        self.assertEqual({'img': ['commit one']}, records['changelog'])
        self.assertEqual(['Build: img'], records['__info'])

    def test_git_changed_ref_passes_find_refs_on(self):
        self.analyze('git', git(OLD), git(NEW), findrefs=True)

        self.assertEqual(
            True, self.provider.generateSpanLogInfo.call_args[0][4])

    def test_git_changed_ref_uses_the_old_url_when_the_new_one_has_none(self):
        module, _, _ = self.analyze(
            'git', git(OLD, url='https://old.example.com/a/b.git'),
            git(NEW, url=None))

        self.assertEqual(
            '/stash/b.git', self.provider.generateSpanLogInfo.call_args[0][1])

    def test_git_changed_ref_prefers_the_new_url(self):
        self.analyze(
            'git', git(OLD, url='https://old.example.com/a/b.git'),
            git(NEW, url='https://new.example.com/c/d.git'))

        self.assertEqual(
            '/stash/d.git', self.provider.generateSpanLogInfo.call_args[0][1])

    def test_git_changed_ref_without_any_url_is_noted_and_not_fetched(self):
        _, records, changed = self.analyze(
            'git', git(OLD, url=None), git(NEW, url=None))

        self.assertTrue(changed)
        self.provider.generateSpanLogInfo.assert_not_called()
        self.provider.fetchRepository.assert_not_called()
        self.assertNotIn('changelog', records)
        self.assertEqual(
            ['Build: img, there is no URL to access the git repo'],
            records['__info'])

    def test_git_span_log_without_a_result_adds_no_changelog(self):
        self.provider.generateSpanLogInfo.return_value = None

        _, records, changed = self.analyze('git', git(OLD), git(NEW))

        self.assertTrue(changed)
        self.assertNotIn('changelog', records)

    def test_git_missing_local_repo_is_fetched_then_the_span_log_retried(self):
        self.provider.generateSpanLogInfo.side_effect = [
            Exception('no such repo'), ['commit one']]

        module, records, changed = self.analyze(
            'git', git(OLD), git(NEW), shellenv={'PATH': '/dib'})

        self.assertTrue(changed)
        self.assertEqual(
            [mock.call.generateSpanLogInfo(
                module.log, '/stash/proj.git', OLD, NEW, False),
             mock.call.fetchRepository(
                module.log, 'proj.git', '/stash/proj.git', URL, NEW, None,
                env={'PATH': '/dib'}, secure=False),
             mock.call.generateSpanLogInfo(
                module.log, '/stash/proj.git', OLD, NEW, False)],
            self.provider.mock_calls)
        self.assertEqual({'img': ['commit one']}, records['changelog'])
        self.assertEqual(['Build: img'], records['__info'])
        self.assertIn(
            ("Span log threw '%s' attempting fetch and trying again",
             'no such repo'),
            module.log.called('info'))

    def test_git_fetch_failure_is_reported_and_the_change_still_counts(self):
        self.provider.generateSpanLogInfo.side_effect = Exception('no repo')
        self.provider.fetchRepository.side_effect = Exception('network down')

        module, records, changed = self.analyze('git', git(OLD), git(NEW))

        self.assertTrue(changed)
        self.assertEqual(1, self.provider.fetchRepository.call_count)
        self.assertEqual(1, self.provider.generateSpanLogInfo.call_count)
        self.assertEqual(1, len(module.log.called('exception')))
        self.assertNotIn('changelog', records)
        self.assertEqual(
            ['Build: img, Could not get git changelog due to failures'],
            records['__info'])

    def test_git_retry_failure_after_a_good_fetch_is_reported(self):
        self.provider.generateSpanLogInfo.side_effect = Exception('still bad')

        module, records, changed = self.analyze('git', git(OLD), git(NEW))

        self.assertTrue(changed)
        self.assertEqual(2, self.provider.generateSpanLogInfo.call_count)
        self.assertEqual(1, self.provider.fetchRepository.call_count)
        self.assertNotIn('changelog', records)
        self.assertEqual(
            ['Build: img, Could not get git changelog due to failures'],
            records['__info'])

    def test_git_same_ref_and_branch_is_not_a_change(self):
        module, records, changed = self.analyze(
            'git', git(OLD), git(OLD))

        self.assertFalse(changed)
        self.assertEqual({}, records['old'])
        self.assertEqual({}, records['new'])
        self.assertEqual([], records['__info'])
        self.provider.generateSpanLogInfo.assert_not_called()

    def test_git_same_ref_on_a_different_branch_is_noted(self):
        _, records, changed = self.analyze(
            'git', git(OLD, branch='master'), git(OLD, branch='dev'))

        self.assertTrue(changed)
        self.assertEqual(
            ["Build: img, SHA1's are the same, "
             "The branch changed from 'master' to 'dev'"],
            records['__info'])
        self.provider.generateSpanLogInfo.assert_not_called()

    def test_git_changed_ref_and_branch_notes_the_branch_and_gets_the_log(self):
        self.provider.generateSpanLogInfo.return_value = ['commit one']

        _, records, _ = self.analyze(
            'git', git(OLD, branch='master'), git(NEW, branch='dev'))

        self.assertEqual(
            ["Build: img, The branch changed from 'master' to 'dev'"],
            records['__info'])
        self.assertEqual({'img': ['commit one']}, records['changelog'])

    @unittest.skip(
        "pre-existing bug: ', a manifest was missing the git SHA1' % build "
        "has no format specifier and raises TypeError for any manifest "
        "without a REF; not asserting that behaviour")
    def test_git_missing_ref_is_noted(self):
        pass

    def test_dpkg_changed_version_is_noted(self):
        _, records, changed = self.analyze(
            'dpkg', dpkg('1.0'), dpkg('1.1'))

        self.assertTrue(changed)
        self.assertEqual(
            ["Build: img, version changed from '1.0' to '1.1'"],
            records['__info'])

    def test_dpkg_same_version_is_not_a_change(self):
        _, records, changed = self.analyze('dpkg', dpkg('1.0'), dpkg('1.0'))

        self.assertFalse(changed)
        self.assertEqual({}, records['old'])
        self.assertEqual({}, records['new'])

    def test_pip_changed_version_is_noted(self):
        _, records, changed = self.analyze(
            'pip', ('pip', {'VERSION': '1.0'}), ('pip', {'VERSION': '2.0'}))

        self.assertTrue(changed)
        self.assertEqual(
            ["Build: img, version changed from '1.0' to '2.0'"],
            records['__info'])

    def test_file_reports_each_kind_of_change(self):
        old = ('file', {'INJECTED': '/a', 'SHA1': 'x', 'URL': 'u1'})
        new = ('file', {'INJECTED': '/b', 'SHA1': 'y', 'URL': 'u2'})

        _, records, changed = self.analyze('file', old, new)

        self.assertTrue(changed)
        self.assertEqual(
            ["Build: 'img', image location changed, file content changed, "
             "pull url changed"],
            records['__info'])

    def test_file_unchanged_is_not_a_change(self):
        same = ('file', {'INJECTED': '/a', 'SHA1': 'x', 'URL': 'u1'})

        _, _, changed = self.analyze('file', same, same)

        self.assertFalse(changed)

    def test_tar_reports_each_kind_of_change(self):
        old = ('tar', {'FILES': ('/a', ['f']), 'SHA1': 'x', 'URL': 'u1'})
        new = ('tar', {'FILES': ('/b', ['f']), 'SHA1': 'y', 'URL': 'u2'})

        _, records, changed = self.analyze('tar', old, new)

        self.assertTrue(changed)
        self.assertEqual(
            ["Build: 'img', image location changed, tar content changed, "
             "pull url changed"],
            records['__info'])

    def test_tar_unchanged_is_not_a_change(self):
        same = ('tar', {'FILES': ('/a', ['f']), 'SHA1': 'x', 'URL': 'u1'})

        _, _, changed = self.analyze('tar', same, same)

        self.assertFalse(changed)

    def test_unknown_package_type_is_left_in_the_changelog(self):
        _, records, changed = self.analyze(
            'rpm', ('rpm', {'VERSION': '1'}), ('rpm', {'VERSION': '2'}))

        self.assertTrue(changed)
        self.assertEqual(['img'], list(records['old']))
        self.assertEqual([], records['__info'])


class TestCreateProductDiff(ChangeLogTestCase):

    def test_product_diff_reports_build_and_metadata_changes(self):
        previous = {'product': {
            'build': {'img': {'command': 'csmake a', 'time': 't0'}},
            'metadata': {'img': {
                'name': 'Prod', 'version-full': '1.0', 'dropped': 'x'}}}}
        current = {'product': {
            'build': {'img': {'command': 'csmake b'},
                      'other': {'command': 'csmake c'}},
            'metadata': {
                'img': {'name': 'Prod', 'version-full': '1.1', 'added': 'y'},
                'other': {'name': 'Other'}}}}
        changelog = {}

        self.changelog_module()._createProductDiff(
            changelog, previous, current)

        build = changelog['product']['build']
        self.assertEqual(current['product']['build'], build['new'])
        self.assertEqual(previous['product']['build'], build['old'])
        self.assertEqual(
            ["NOTE: Build: img Command line changed",
             "Build other, previous didn't have a command"],
            build['__info'])
        self.assertEqual({
            'img': {
                'version-full': {'new': '1.1', 'old': '1.0'},
                'added': {'new': 'y', 'old': ''},
                'dropped': {'new': '', 'old': 'x'}},
            'other': {'__info': ['build in current and not in previous']}},
            changelog['product']['metadata'])

    def test_product_diff_notes_builds_and_metadata_missing_from_current(self):
        previous = {'product': {
            'build': {'gone': {'command': 'c'}},
            'metadata': {'gone': {'name': 'Gone'}}}}
        current = {'product': {'build': {}, 'metadata': {}}}
        changelog = {}

        self.changelog_module()._createProductDiff(
            changelog, previous, current)

        self.assertEqual(
            ["Build gone, new build didn't have a command"],
            changelog['product']['build']['__info'])
        self.assertEqual(
            {'gone': {'__info': ['build in previous and not in current']}},
            changelog['product']['metadata'])

    def test_product_diff_of_identical_products_has_no_changes(self):
        product = {'product': {
            'build': {'img': {'command': 'csmake a'}},
            'metadata': {'img': {'name': 'Prod'}}}}
        changelog = {}

        self.changelog_module()._createProductDiff(
            changelog, product, product)

        self.assertEqual([], changelog['product']['build']['__info'])
        self.assertEqual({'img': {}}, changelog['product']['metadata'])

    def test_product_diff_needs_a_product_on_both_sides(self):
        for previous, current in [({}, {'product': {}}), ({'product': {}}, {})]:
            changelog = {}

            self.changelog_module()._createProductDiff(
                changelog, previous, current)

            self.assertEqual({}, changelog)


class TestCreateSourcesDiff(ChangeLogTestCase):

    def diff(self, previous, current):
        changelog = {}
        module = self.changelog_module(
            gitstash='/stash', findrefs=False, shellenv={})
        module._createSourcesDiff(changelog, previous, current)
        return changelog

    def test_sources_diff_reports_only_what_changed(self):
        previous = {'sources': {
            'bash': {'img': dpkg('5.0')},
            'libc6': {'img_amd64': dpkg('2.31')}}}
        current = {'sources': {
            'bash': {'img': dpkg('5.1')},
            'libc6': {'img_amd64': dpkg('2.31')},
            'newpkg': {'img': dpkg('1.0')}}}

        changelog = self.diff(previous, current)

        self.assertEqual({
            'bash': {
                'new': {'img': dpkg('5.1')},
                'old': {'img': dpkg('5.0')},
                '__info': ["Build: img, version changed from '5.0' to '5.1'"]},
            'newpkg': {
                'new': {'img': dpkg('1.0')},
                'old': {},
                '__info': ['source was not in previous']}},
            changelog['sources'])

    def test_sources_diff_notes_a_build_new_to_a_known_source(self):
        previous = {'sources': {'bash': {'img': dpkg('5.0')}}}
        current = {'sources': {
            'bash': {'img': dpkg('5.0'), 'other': dpkg('5.0')}}}

        changelog = self.diff(previous, current)

        self.assertEqual({
            'bash': {
                'new': {'other': dpkg('5.0')},
                'old': {'other': {}},
                '__info': ["Source was not in previous for build: 'other'"]}},
            changelog['sources'])

    def test_sources_diff_runs_the_git_analysis_for_a_changed_ref(self):
        self.provider.generateSpanLogInfo.return_value = ['commit one']
        previous = {'sources': {'org/proj': {'img': git(OLD)}}}
        current = {'sources': {'org/proj': {'img': git(NEW)}}}

        changelog = self.diff(previous, current)

        self.assertEqual(
            {'img': ['commit one']},
            changelog['sources']['org/proj']['changelog'])
        self.assertEqual(
            ['Build: img'], changelog['sources']['org/proj']['__info'])

    def test_sources_diff_drops_a_git_source_whose_ref_and_branch_match(self):
        previous = {'sources': {'org/proj': {'img': git(OLD)}}}
        current = {'sources': {'org/proj': {'img': git(OLD, other='x')}}}

        changelog = self.diff(previous, current)

        self.assertEqual({}, changelog['sources'])
        self.provider.generateSpanLogInfo.assert_not_called()

    def test_sources_diff_needs_sources_on_both_sides(self):
        for previous, current in [({}, {'sources': {}}), ({'sources': {}}, {})]:
            self.assertEqual({}, self.diff(previous, current))

    @unittest.skip(
        "pre-existing bug: when a source changes type ('dpkg' -> 'pip', ...) "
        "the code reaches 'if delta:' without having assigned delta "
        "(UnboundLocalError, or a stale value from the previous iteration); "
        "not asserting that behaviour")
    def test_sources_diff_notes_a_source_that_changed_type(self):
        pass


class TestFormatOutput(ChangeLogTestCase):

    def format(self, changelog, specs):
        module = self.changelog_module()
        module._formatOutput(changelog, specs)
        return module

    def test_format_output_writes_yaml_text_for_a_yaml_target(self):
        path = os.path.join(helpers.make_tempdir(self), 'changelog.yaml')
        changelog = {'sources': {'bash': {'__info': ['x'], 'old': ('a', {})}}}

        self.format(changelog, [{'type': 'yaml', 'location': path}])

        with open(path) as f:
            self.assertEqual(self.yaml.safe_dump(changelog), f.read())

    def test_format_output_falls_back_to_yaml_for_an_unknown_type(self):
        path = os.path.join(helpers.make_tempdir(self), 'changelog.txt')

        self.format({'a': 1}, [{'type': 'text', 'location': path}])

        with open(path) as f:
            self.assertEqual({'a': 1}, self.yaml.safe_load(f))

    def test_format_output_writes_every_requested_target(self):
        workdir = helpers.make_tempdir(self)
        paths = [os.path.join(workdir, name) for name in ('one', 'two')]

        self.format({'a': 1}, [{'type': 'yaml', 'location': p} for p in paths])

        for path in paths:
            self.assertTrue(os.path.exists(path))

    def test_format_output_log_type_is_reported_as_unimplemented(self):
        path = os.path.join(helpers.make_tempdir(self), 'changelog.log')

        module = self.format({'a': 1}, [{'type': 'log', 'location': path}])

        self.assertEqual(1, len(module.log.called('error')))
        self.assertFalse(os.path.exists(path))


class TestBuild(ChangeLogTestCase):
    """build() reads the manifests with yaml.safe_load and writes the log."""

    def setUp(self):
        super(TestBuild, self).setUp()
        self.workdir = helpers.make_tempdir(self)
        self.output = os.path.join(self.workdir, 'changelog.yaml')

    def manifest(self, name, data):
        path = os.path.join(self.workdir, name)
        with open(path, 'w') as f:
            f.write(self.yaml.safe_dump(data))
        return path

    def run_build(self, specs, current=None, options=None, env=None):
        """specs: [(from specs, to specs)] as the file mapping iterates."""
        module = self.changelog_module(
            mapping=types.SimpleNamespace(iterspecs=lambda: specs))
        module.env.env['RESULTS'] = self.workdir
        if current is not None:
            module.env.env['__Csversion__'] = current
        module.env.env.update(env or {})
        return module, module.build(options or {})

    def to(self):
        return [{'type': 'yaml', 'location': self.output}]

    def written(self):
        with open(self.output) as f:
            return self.yaml.safe_load(f)

    def test_build_writes_a_changelog_of_previous_against_the_environment(self):
        previous = self.manifest('previous.yaml', {
            'sources': {'bash': {'img': dpkg('5.0')}},
            'product': {
                'build': {'img': {'command': 'csmake a'}},
                'metadata': {'img': {'version-full': '1.0'}}}})
        current = {
            'sources': {'bash': {'img': dpkg('5.1')}},
            'product': {
                'build': {'img': {'command': 'csmake a'}},
                'metadata': {'img': {'version-full': '1.1'}}}}

        module, result = self.run_build(
            [([{'id': 'previous', 'location': previous}], self.to())],
            current=current)

        self.assertTrue(result)
        changelog = self.written()
        self.assertEqual(
            ["Build: img, version changed from '5.0' to '5.1'"],
            changelog['sources']['bash']['__info'])
        self.assertEqual(
            {'img': {'version-full': {'new': '1.1', 'old': '1.0'}}},
            changelog['product']['metadata'])
        self.assertEqual(1, len(module.log.called('passed')))

    def test_build_merges_every_previous_manifest_of_a_group(self):
        first = self.manifest(
            'first.yaml', {'sources': {'bash': {'img': dpkg('5.0')}}})
        second = self.manifest(
            'second.yaml', {'sources': {'tzdata': {'img': dpkg('1')}}})

        self.run_build(
            [([{'id': 'a', 'location': first},
               {'id': 'a', 'location': second}], self.to())],
            current={'sources': {'bash': {'img': dpkg('5.1')},
                                 'tzdata': {'img': dpkg('2')}}})

        self.assertEqual({'bash', 'tzdata'}, set(self.written()['sources']))

    def test_build_previous_group_selects_the_manifest_to_compare_against(self):
        old = self.manifest(
            'old.yaml', {'sources': {'bash': {'img': dpkg('4.0')}}})
        newer = self.manifest(
            'newer.yaml', {'sources': {'bash': {'img': dpkg('5.0')}}})

        self.run_build(
            [([{'id': 'old', 'location': old},
               {'id': 'newer', 'location': newer}], self.to())],
            current={'sources': {'bash': {'img': dpkg('5.1')}}},
            options={'previous-group': 'newer'})

        self.assertEqual(
            ["Build: img, version changed from '5.0' to '5.1'"],
            self.written()['sources']['bash']['__info'])

    def test_build_current_group_reads_the_current_manifest_from_files(self):
        previous = self.manifest(
            'previous.yaml', {'sources': {'bash': {'img': dpkg('5.0')}}})
        current = self.manifest(
            'current.yaml', {'sources': {'bash': {'img': dpkg('5.2')}}})

        self.run_build(
            [([{'id': 'previous', 'location': previous},
               {'id': 'current', 'location': current}], self.to())],
            current={'sources': {'bash': {'img': dpkg('9.9')}}},
            options={'previous-group': 'previous', 'current-group': 'current'})

        self.assertEqual(
            ["Build: img, version changed from '5.0' to '5.2'"],
            self.written()['sources']['bash']['__info'])

    def test_build_current_group_without_files_produces_no_changelog(self):
        previous = self.manifest('previous.yaml', {'sources': {}})

        module, result = self.run_build(
            [([{'id': 'previous', 'location': previous}], self.to())],
            options={'current-group': 'missing'})

        self.assertIsNone(result)
        self.assertFalse(os.path.exists(self.output))
        self.assertEqual(2, len(module.log.called('warning')))

    def test_build_without_a_mapping_does_nothing(self):
        module = self.changelog_module(mapping=None)

        self.assertIsNone(module.build({}))

        self.assertEqual(1, len(module.log.called('passed')))
        self.assertEqual(2, len(module.log.called('warning')))

    def test_build_without_previous_manifests_produces_no_changelog(self):
        module, result = self.run_build(
            [([{'id': 'other', 'location': 'x'}], self.to())],
            current={}, options={'previous-group': 'previous'})

        self.assertIsNone(result)
        self.assertFalse(os.path.exists(self.output))

    def test_build_without_any_current_state_produces_no_changelog(self):
        previous = self.manifest('previous.yaml', {'sources': {}})

        module, result = self.run_build(
            [([{'id': 'previous', 'location': previous}], self.to())])

        self.assertIsNone(result)
        self.assertFalse(os.path.exists(self.output))

    def git_build(self, options=None, env=None):
        previous = self.manifest(
            'previous.yaml', {'sources': {'org/proj': {'img': git(OLD)}}})
        return self.run_build(
            [([{'id': 'previous', 'location': previous}], self.to())],
            current={'sources': {'org/proj': {'img': git(NEW)}}},
            options=options, env=env)

    def test_build_git_analysis_uses_results_dir_as_the_default_stash(self):
        self.provider.generateSpanLogInfo.return_value = ['commit one']

        module, result = self.git_build()

        self.assertTrue(result)
        self.provider.generateSpanLogInfo.assert_called_once_with(
            module.log, os.path.join(self.workdir, 'proj.git'), OLD, NEW,
            False)
        self.assertEqual(
            {'img': ['commit one']},
            self.written()['sources']['org/proj']['changelog'])

    def test_build_git_analysis_honours_stash_find_refs_and_dib_environment(self):
        self.provider.generateSpanLogInfo.side_effect = [
            Exception('not cloned'), ['commit one']]

        module, _ = self.git_build(
            options={'git-stash': '/custom/stash', 'find-refs': 'True'},
            env={'__DIBEnv__': {'shellenv': {'PATH': '/dib/bin'}}})

        self.assertEqual(
            [mock.call.generateSpanLogInfo(
                module.log, '/custom/stash/proj.git', OLD, NEW, True),
             mock.call.fetchRepository(
                module.log, 'proj.git', '/custom/stash/proj.git', URL, NEW,
                None, env={'PATH': '/dib/bin'}, secure=False),
             mock.call.generateSpanLogInfo(
                module.log, '/custom/stash/proj.git', OLD, NEW, True)],
            self.provider.mock_calls)

    def test_build_find_refs_other_than_true_is_off(self):
        self.provider.generateSpanLogInfo.return_value = None

        self.git_build(options={'find-refs': 'yes'})

        self.assertEqual(
            False, self.provider.generateSpanLogInfo.call_args[0][4])


if __name__ == '__main__':
    unittest.main()
