# <copyright>
# (c) Copyright 2017 Hewlett Packard Enterprise Development LP
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
# <copyright>
# (c) Copyright 2017 Hewlett Packard Enterprise Development LP
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
from CsmakeCore.CsmakeModule import CsmakeModule
from CsmakeProviders.GitProvider import GitProvider
from datetime import datetime
import sys
import yaml
import os
import os.path

class CsversionGenerateChangeLog(CsmakeModule):
    """Purpose: Create a change log from the mapping provided.
                Unless otherwise specified, the change log will
                be between the current state and the manifest
                provided in a mapping.  See "Options" for details
                This module should run after product metadata is
                finished.

    Options: previous-group - (OPTIONAL) This will define the group
                 to pull the manifest from.
                 (the group being the group id of the manifest to use
                  from the file mapping.  If multiple files match
                  the manifests will be grouped together allowing for
                  partial manifests to be generated into a single changelog)
                 Default is all files provided in mapping will be
                  used.  If a 1-1 mapping is specified, this can
                  produce several change logs at one time.
             current-group - (OPTIONAL) This will define the group
                 to compare the manifest "previous" against.
                 (the group being the group od of the manifest to use
                  from the file mapping, one will be picked.)
                 Default is to use the in memory __Csversion__ information
             git-stash - (OPTIONAL) If there is a location for git repos
                 that can be used to speed up the git delta generation
                 then point 'git-stash' to that location.
                 Default is %(RESULTS)s
             find-refs - (OPTIONAL) This will add related references
                 to the output when True - this may slow the build down a lot,
                 but will provide all gerrit review tags, for example,
                 which could be extremely useful
                 Default is False

    Mapping: Use **maps to map manifests into a change log on the right.
             Only files with a type of yaml and a purpose of manifest
             are accepted as inputs.
             Output will be based on the type(s) given for the output
                files.  Currently supported are 'yaml' and 'log'
                a file type that does not match the supported types
                will output a yaml file.
    Uses Environment:
        __Csversion__ - A dictionary where product metadata is stored under
                        'product'.  'product' is product info keyed off of
                        the type of data stored, i.e., metadata and build.
                        The same metadata/tag combination will be overwritten
                        if pulled twice.
                        The structure of the product dictionary is
                        a dictionary of tags from builds with metadata and
                        build information.
        __DIBEnv__ - If available, the git fetch will use the environment
                     from the DIB shell to maintain consistency within the build
                     When not available, the execution shell environment will
                     be used.
        """

    def _formatOutput(self, changelog, tofiles):
        class _TypeSetter:
            #TODO: Consider pulling this out so that other report types
            #      could be supported by subclassing
            def yaml(innerself, spec):
                yamltext = yaml.safe_dump(changelog)
                with open(spec['location'],'w') as log:
                    log.write(yamltext)

            def log(innerself, spec):
                self.log.error("TODO: create a human readable changelog file - requested but not implemented")
                #Do fancy stuff that Shelly would rather read
                #TODO: Lots of fancy formatting...

        ts = _TypeSetter()
        for spec in tofiles:
            #TODO: Consider adding type__intent
            if hasattr(ts, spec['type']):
                getattr(ts, spec['type'])(spec)
            else:
                getattr(ts, 'yaml')(spec)

    def _analyzeSpecificChange(self, packageType, records, build):
        self.log.devdebug("records: %s", str(records))
        old = records['old'][build][1]
        new = records['new'][build][1]
        class _PackageAnalyzer:
            def git(innerself):
                info = "Build: %s" % build
                delta = False

                url = None
                newref = None
                oldref = None
                if 'REF' not in old or 'REF' not in new:
                    info += ", a manifest was missing the git SHA1" % build
                    delta = True
                elif old['REF'] != new['REF']:
                    if 'URL' in new:
                        url = new['URL']
                    elif 'URL' in old:
                        url = old['URL']
                    if url is None:
                        info += ", there is no URL to access the git repo"
                    delta = True
                    newref = new['REF']
                    oldref = old['REF']
                else:
                    info += ", SHA1's are the same"

                if 'BRANCH' not in old or 'BRANCH' not in new \
                    or old['BRANCH'] != new['BRANCH']:
                    info += ", The branch changed from '%s' to '%s'" % (
                        old['BRANCH'],
                        new['BRANCH'] )
                    delta = True

                #get the sha delta from GitProvider
                if delta and url is not None:
                    _, name = os.path.split(url)
                    localrepo = os.path.join(
                        self.gitstash,
                        name )
                    result = None
                    try:
                        result = GitProvider.generateSpanLogInfo(
                            self.log,
                            localrepo,
                            oldref,
                            newref,
                            self.findrefs )
                    except Exception as e:
                        self.log.info("Span log threw '%s' attempting fetch and trying again", str(e))
                        try:
                            GitProvider.fetchRepository(
                                self.log,
                                name,
                                localrepo,
                                url,
                                newref,
                                None,
                                env=self.shellenv,
                                secure=False )
                            result = GitProvider.generateSpanLogInfo(
                                self.log,
                                localrepo,
                                oldref,
                                newref,
                                self.findrefs )
                        except:
                            self.log.exception("Attempt to generate git changelog failed")
                            info += ", Could not get git changelog due to failures"
                    if result is not None:
                        if 'changelog' not in records:
                            records['changelog'] = {}
                        records['changelog'][build] = result

                if delta:
                    records['__info'].append(info)
                return delta

            def dpkg(innerself):
                delta = 'VERSION' in old and 'VERSION' in new \
                       and old['VERSION'] != new['VERSION']
                if delta:
                    records['__info'].append(
                        "Build: %s, version changed from '%s' to '%s'" % (
                            build,
                            old['VERSION'],
                            new['VERSION'] ) )
                return delta

            def pip(innerself):
                delta = 'VERSION' in old and 'VERSION' in new \
                       and old['VERSION'] != new['VERSION']
                if delta:
                    records['__info'].append(
                        "Build: %s, version changed from '%s' to '%s'" % (
                            build,
                            old['VERSION'],
                            new['VERSION'] ) )
                return delta

            def file(innerself):
                info = "Build: '%s'" % build
                delta = False
                if 'INJECTED' not in old or 'INJECTED' not in new \
                       or old['INJECTED'] != new['INJECTED']:
                    info += ", image location changed"
                    delta = True
                if 'SHA1' not in old or 'SHA1' not in new \
                       or old['SHA1'] != new['SHA1']:
                    info += ", file content changed"
                    delta = True
                if 'URL' not in old or 'URL' not in new \
                       or old['URL'] != new['URL']:
                    info += ", pull url changed"
                    delta = True
                if delta:
                    records['__info'].append(info)
                return delta

            def tar(innerself):
                info = "Build: '%s'" % build
                delta = False
                if 'FILES' not in old or 'FILES' not in new \
                        or old['FILES'][0] != new['FILES'][0]:
                    info += ", image location changed"
                    delta = True
                if 'SHA1' not in old or 'SHA1' not in new \
                        or old['SHA1'] != new['SHA1']:
                    info += ", tar content changed"
                    delta = True
                if 'URL' not in old or 'URL' not in new \
                        or old['URL'] != new['URL']:
                    info += ", pull url changed"
                    delta = True
                if delta:
                    records['__info'].append(info)
                return delta

        pa = _PackageAnalyzer()
        if hasattr(pa, packageType):
            if not getattr(pa, packageType)():
                #records['__info'].append("Build: %s, shows no actual diff (TODO: remove from changelog)" % build)
                #TODO: Analysis shows no real change - delete the build record
                del records['old'][build]
                del records['new'][build]

        return len(records['old']) != 0 or len(records['new']) != 0

    def _createProductDiff(self, changelog, previous, current):
        if 'product' not in previous or 'product' not in current:
            return
        changelog['product']={
            'build': {
                'new' : current['product']['build'],
                'old' : previous['product']['build'],
                '__info' : [] } }
        for build, values in current['product']['build'].items():
            if build not in previous['product']['build']:
                changelog['product']['build']['__info'].append(
                    "Build %s, previous didn't have a command" % build )
                continue

            if values['command'] != \
               previous['product']['build'][build]['command']:
                changelog['product']['build']['__info'].append("NOTE: Build: %s Command line changed" % build)

        for build in previous['product']['build'].keys():
            if build not in current['product']['build']:
                changelog['product']['build']['__info'].append(
                    "Build %s, new build didn't have a command" % build )

        changelog['product']['metadata']={}
        changemeta = changelog['product']['metadata']
        for build, metadata in current['product']['metadata'].items():
            if build not in previous['product']['metadata']:
                changemeta[build] = {
                    '__info' : ['build in current and not in previous'] }
                continue
            changemeta[build] = {}
            for key, value in metadata.items():
                if key not in previous['product']['metadata'][build]:
                    changemeta[build][key] = {
                        'new':value,
                        'old':"" }
                elif previous['product']['metadata'][build][key] != value:
                    changemeta[build][key] = {
                        'new':value,
                        'old':previous['product']['metadata'][build][key] }
            for key, value in previous['product']['metadata'][build].items():
                if key not in metadata:
                    changemeta[build][key] = {
                        'new':"",
                        'old':value }

        for build in previous['product']['metadata'].keys():
            if build not in current['product']['metadata']:
                changemeta[build] = {
                    '__info': ['build in previous and not in current'] }
        self.log.devdebug("Changelog after product: %s", str(changelog))

    def _createSourcesDiff(self, changelog, previous, current):
        if 'sources' not in previous or 'sources' not in current:
            return
        changesource = {}
        changelog['sources'] = changesource
        for source, builds in current['sources'].items():
            if source not in previous['sources']:
                changesource[source] = {
                    'new':builds,
                    'old':{},
                    '__info': ['source was not in previous'] }
                continue
            for build, info in builds.items():
                if build not in previous['sources'][source]:
                    if source not in changesource:
                        changesource[source] = {
                            'new':{},
                            'old':{},
                            '__info': [] }
                    changesource[source]['new'][build] = info
                    changesource[source]['old'][build] = {}
                    changesource[source]['__info'].append(
                        "Source was not in previous for build: '%s'" % build )
                else:
                    previnfo = previous['sources'][source][build]
                    if info[0] != previnfo[0]:
                        if source not in changesource:
                            changesource[source] = {
                                'new':{},
                                'old':{},
                                '__info': [] }
                        changesource[source]['new'][build] = info
                        changesource[source]['old'][build] = previnfo
                        changesource[source]['__info'].append(
                            "Source changed formats for build: '%s'" % build )
                    else:
                        delta = False
                        for key, value in info[1].items():
                            self.log.devdebug("previnfo: %s", str(previnfo))
                            if key not in previnfo[1]:
                                if source not in changesource:
                                    changesource[source] = {
                                        'new':{},
                                        'old':{},
                                        '__info': [] }
                                changesource[source]['new'][build] = info
                                changesource[source]['old'][build] = previnfo
                                changesource[source]['__info'].append(
                                    "Format description changed for '%s' in build: '%s'" % (
                                        info[0],
                                        build ) )
                                delta = True
                            elif value != previnfo[1][key]:
                                if source not in changesource:
                                    changesource[source] = {
                                        'new':{},
                                        'old':{},
                                        '__info':[] }
                                changesource[source]['new'][build] = info
                                changesource[source]['old'][build] = previnfo
                                delta = True
                            if delta:
                                break
                        if not delta:
                            for key in previnfo[1].keys():
                                if key not in info[1]:
                                    if source not in changesource:
                                        changesource[source] = {
                                            'new':{},
                                            'old':{},
                                            '__info':[] }
                                    changesource[source]['new'][build] = info
                                    changesource[source]['old'][build] = previnfo
                                    changesource[source]['__info'].append(
                                        "Format description changed for '%s' in build: '%s'" % (
                                            info[0],
                                            build ) )
                                    delta = True
                    if delta:
                        #dispatch specific info[0] analysis (package specific)
                        if not self._analyzeSpecificChange(
                            info[0],
                            changesource[source],
                            build ):
                            del changesource[source]

    def build(self, options):
        if self.mapping is None:
            self.log.warning("**maps was not specified in section.  Nothing to do...")
            self.log.warning("   No changelog will be produced")
            self.log.passed()
            return None

        previousGroup = None
        if 'previous-group' in options:
            previousGroup = options['previous-group']

        currentGroup = None
        if 'current-group' in options:
            currentGroup = options['current-group']

        self.gitstash = self.env.env['RESULTS']
        if 'git-stash' in options:
            self.gitstash = options['git-stash']

        self.findrefs = False
        if 'find-refs' in options:
            self.findrefs = options['find-refs'] == 'True'

        self.shellenv = os.environ
        if '__DIBEnv__' in self.env.env:
            if 'shellenv' in self.env.env['__DIBEnv__']:
                self.shellenv = self.env.env['__DIBEnv__']['shellenv']

        groupings = []
        for (fromSpecs, toSpecs) in self.mapping.iterspecs():
            current = {'previous':[], 'current':[]}
            groupings.append(current)
            for fromSpec in fromSpecs:
                if previousGroup is None or previousGroup == fromSpec['id']:
                    current['previous'].append(fromSpec)
                if currentGroup is not None and currentGroup == fromSpec['id']:
                    current['current'].append(fromSpec)
            current['to'] = toSpecs

        for group in groupings:
            previous = {}
            for spec in group['previous']:
                with open(spec['location']) as f:
                    mani = yaml.safe_load(f)
                previous.update(mani)
            if len(previous) == 0:
                self.log.warning("**maps did not yield any manifests to map")
                self.log.warning("   No changelog will be produced")
                self.log.passed()
                return None
            current = {}
            if currentGroup is not None:
                if len(group['current']) == 0:
                    self.log.warning(
                        "The specified current-group '%s' didn't have any files in the map",
                        currentGroup )
                    self.log.warning(
                        "    No changelog will be produced" )
                    self.log.passed()
                    return None
                for spec in group['current']:
                    with open(spec['location']) as f:
                        mani = yaml.safe_load(f)
                    current.update(mani)
                if len(current) == 0:
                    self.log.warning(
                        "A current-group was specified but no manifests were found")
                    self.log.warning(
                        "    No changelog will be produced" )
                    self.log.passed()
                    return None

            else:
                if '__Csversion__' not in self.env.env:
                    self.log.warning(
                        "A current-group was not specified, and there is no internal build state to reference")
                    self.log.warning(
                        "    No changelog will be produced" )
                    return None
                current = self.env.env['__Csversion__']
            changelog = {}
            self._createProductDiff(changelog, previous, current)
            self._createSourcesDiff(changelog, previous, current)
            self._formatOutput(changelog, toSpecs)

        self.log.passed()
        return True
