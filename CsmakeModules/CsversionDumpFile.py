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
from Csmake.CsmakeAspect import CsmakeAspect

class CsversionDumpFile(CsmakeAspect):
    """Purpose: Dumps repo versions saved to a file
          Note: intended attached to the DIB process
    Options: sources-file - location to write the file with 'sources'
                            information
             version-file - location to write the file with
                            'product'/'metadata' information
             build-file - location to write the file with
                            'product'/'build' information
             version-tags - (OPTIONAL) tags to output and order
                          if unspecified, all tags saved will be output
    Phase: sources, build
    Joinpoint: passed
    Creates Environment:
        __Csversion__ - a dictionary of version info keyed off of
                        the repo name and then the tag.
                        The same repo/tag combination will be overwritten
                        if pulled twice (with a warning)
                        Every element in the dictionary is a dictionary
                        of tags contiaing a tuple:
                        (<repo-type>, <value-dict>)
        """

    REQUIRED_OPTIONS = ['sources-file', 'version-file', 'build-file']

    def start__build(self, phase, options, section, sectionoptions):
        sources=False
        version=False
        build=False
        if '__Csversion__' not in self.env.env:
            self.log.error("There was no csversion information recorded")
            self.log.failed()
            return False

        versinfo = self.env.env['__Csversion__']

        sources = 'sources' in versinfo
        version = 'product' in versinfo and 'metadata' in versinfo['product']
        build = 'product' in versinfo and 'build' in versinfo['product']

        if not (sources or version or build):
            self.log.error("There was no csversion information recorded")
            self.log.failed()
            return False

        if sources:
            gitprefix = "git: %s: REPO: %s  %%s\n"
            gitorder = ['NAME', 'BRANCH', 'REF', 'INJECTED']
            fileprefix = "file: %s: %%s\n"
            fileorder = ['NAME', 'BUILD_INDEX', 'SHA1', 'TIME', 'INJECTED']
            tarprefix = "tar: %s: %%s\n"
            tarorder = ['NAME', 'BUILD_INDEX', 'SHA1', 'TIME']
            self._ensureDirectoryExists(options['sources-file'])
            with open(options['sources-file'], 'w') as csversionfile:
                for repo, tagdict in versinfo['sources'].items():
                    for tag, value in tagdict.items():
                        pulltype, pullvalues = value
                        if pulltype == 'git':
                            line = gitprefix % (tag, repo)
                            parts = []
                            for item in gitorder:
                                if item in pullvalues:
                                    parts.append("  %s: %s" % (
                                        item,
                                        pullvalues[item] ) )
                            line = line % ''.join(parts)
                            csversionfile.write(line)
                        elif pulltype == 'file':
                            line = fileprefix % tag
                            parts = []
                            for item in fileorder:
                                if item in pullvalues:
                                    parts.append("  %s: %s" % (
                                        item,
                                        pullvalues[item] ) )
                            line = line % ''.join(parts)
                            csversionfile.write(line)
                        elif pulltype == 'tar':
                            line = tarprefix % tag
                            parts = []
                            for item in fileorder:
                                if item in pullvalues:
                                    parts.append("  %s: %s" % (
                                        item,
                                        pullvalues[item] ) )
                            line = line % ''.join(parts)
                            line = line + "  INJECTED: %s\n" % pullvalues['FILES'][0]
                            csversionfile.write(line)
                            for filename in pullvalues['FILES'][1]:
                                csversionfile.write("    %s\n" % filename)

        if version:
            metadataDicts = versinfo['product']['metadata']
            versionorder = [
                ('name', 'PRODUCT'),
                ('version-full', 'VERSION'),
                ('HELION_VERSION', "HELION VERSION"),
                ('APPLIANCE_DESCRIPTION', 'APPLIANCE'),
                ('description', 'PRODUCT DESCRIPTION')]
            tagorder = None
            if 'version-tags' in options:
                tagorder = ','.join(options['version-tags'].split('\n')).split(',')
            if tagorder is None:
                tagorder = metadataDicts.keys()
            with open(options['version-file'], 'w') as csversionfile:
                for tag in tagorder:
                    if tag not in metadataDicts:
                        self.log.warning("version-tag '%s' was specified but not defined", tag)
                        continue
                    csversionfile.write("Product information for: %s\n" % tag)
                    lines = []
                    for orderitemkey, label in versionorder:
                        if orderitemkey in metadataDicts[tag]:
                            lines.append("    %s=%s" % (
                                label,
                                metadataDicts[tag][orderitemkey] ) )
                    csversionfile.write('\n'.join(lines))
                    csversionfile.write('\n')

        if build:
            buildDicts = versinfo['product']['build']
            buildorder = [
                ('WRAPPER', "BUILD_WRAPPER"),
                ("BUILD", "BUILD_NUMBER"),
                ("time", "BUILD_DATE_and_TIME"),
                ('command', "BUILD_COMMAND")]
            with open(options['build-file'], 'w') as csversionfile:
                for tag in buildDicts.keys():
                    lines = []
                    for orderitemkey, label in buildorder:
                        if orderitemkey in buildDicts[tag]:
                            lines.append("    %s_%s=%s" % (
                                tag,
                                label,
                                buildDicts[tag][orderitemkey]))
                    csversionfile.write('\n'.join(lines))
                    csversionfile.write('\n')
                csversionfile.write('\nOther information about the builds\n')
        self.log.passed()
        return True
