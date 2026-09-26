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
from Csmake.CsmakeModule import CsmakeModule
from datetime import datetime
import sys

class CsversionCaptureMetadata(CsmakeModule):
    """Purpose: Record the version of the product and current build
                information and other product metadata
                This module must run after product metadata is
                run.
    Options: tag - Provides a context name for the information
                   for example - cs-mgmt-base-image or cs-mgmt-sources
             amend - (OPTIONAL) When True, the current metadata information
                                will not be re0placed, but amended with
                                only the new information provided by the
                                version and build options.
             version_<key> - Information to include about the product
                             Empty strings will be ignored.
             build_<key> - Information to include about the build
                           Empty strings will be ignored.
    Creates Environment:
        __Csversion__ - A dictionary where product metadata is stored under
                        'product'.  'product' is product info keyed off of
                        the type of data stored, i.e., metadata and build.
                        The same metadata/tag combination will be overwritten
                        if pulled twice.
                        The structure of the product dictionary is
                        a dictionary of tags from builds with metadata and
                        build information.
        """

    REQUIRED_OPTIONS = ['tag']

    def build(self, options):
        amend = 'amend' in options and options['amend'] == 'True'
        if '__Csversion__' not in self.env.env:
            self.env.env['__Csversion__'] = {}
            self.log.debug("__Csversion__ not found creating new")
        if 'product' not in self.env.env['__Csversion__']:
            self.env.env['__Csversion__']['product'] = {}
            self.log.debug("product not found, creating new")
        versdict = self.env.env['__Csversion__']['product']
        if 'metadata' not in versdict:
            if amend:
                self.log.error("Nothing to amend - change the amend option to False")
                self.log.failed()
                return None
            versdict['metadata'] = {}
            self.log.debug("metadata not found, creating new")
        else:
            if options['tag'] in versdict['metadata']:
                if amend:
                    self.log.info("metadata, Tag: %s :: Amending",
                        options['tag'] )
                else:
                    self.log.warning("metadata, Tag: %s :: Overwriting %s",
                        options['tag'],
                        str(versdict['metadata'][options['tag']] ))
        if amend:
            if options['tag'] not in versdict['metadata']:
                self.log.error("Nothing to amend - change the amend option to False")
                self.log.failed()
                return None
            else:
                metadict = versdict['metadata'][options['tag']]
        else:
            metadict = self.metadata._getMetadataDefinitions()
            versdict['metadata'][options['tag']] = metadict
            metadict['version-full'] = self.metadata._getDefaultDefinedVersion()


        versdict = self.env.env['__Csversion__']['product']
        if 'build' not in versdict:
            if amend:
                self.log.error("Nothing to amend - change the amend option to False")
                self.log.failed()
                return None
            versdict['build'] = {}
            self.log.debug("build data not found, creating new")
        else:
            if options['tag'] in versdict['build']:
                self.log.warning("build, Tag: %s :: Overwriting %s",
                    options['tag'],
                    str(versdict['build'][options['tag']]) )
        if amend:
            if options['tag'] not in versdict['build']:
                self.log.error("Nothing to amend - change the amend option to False")
                self.log.failed()
                return None
            else:
                builddict=versdict['build'][options['tag']]
        else:
            t = datetime.utcnow().isoformat()
            # snip off microseconds and add a 'Z' for UTC time, e.g.:
            # '2016-07-18T21:48:06.693534' becomes '2016-07-18T21:48:06Z'
            t = t[0:t.rindex('.')] + 'Z'
            builddict = {
                'time' : t,
                'command' : ' '.join(sys.argv) }
            versdict['build'][options['tag']] = builddict
        for name, option in options.items():
            option = option.strip()
            if len(option) == 0:
                continue
            if name.startswith('build_'):
                mykey = name.split('build_')[1].strip()
                builddict[mykey] = option.strip()
            elif name.startswith('version_'):
                mykey = name.split('version_')[1].strip()
                metadict[mykey] = option.strip()

        added = "Amended" if amend else "Added"
        self.log.info("metadata, Tag: %s :: %s %s",
            options['tag'],
            added,
            str(metadict))
        self.log.info("build, Tag: %s :: %s %s",
            options['tag'],
            added,
            str(builddict))
        self.log.passed()
        return True
