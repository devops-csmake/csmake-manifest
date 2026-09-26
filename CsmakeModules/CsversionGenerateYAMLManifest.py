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
import yaml
import os.path

class CsversionGenerateYAMLManifest(CsmakeModule):
    """Purpose: Record the version of the product and current build
                information and other product metadata as an external
                YAML manifest.
                This module must run after product metadata is
                finished.
                
    Options: None
    Mapping: Use **yields-files to map the manifest to an output
    Uses Environment:
        __Csversion__ - A dictionary where product metadata is stored under
                        'product'.  'product' is product info keyed off of
                        the type of data stored, i.e., metadata and build.
                        The same metadata/tag combination will be overwritten
                        if pulled twice.
                        The structure of the product dictionary is 
                        a dictionary of tags from builds with metadata and
                        build information.
        """

    def build(self, options):
        if self.yieldsfiles is None:
            self.log.warning("**yields-files was not specified in section.  Nothing to do...")
            self.log.warning("   No manifest will be produced")
            self.log.passed()
            return None

        locations = []
        for fileindex in self.yieldsfiles:
            location = fileindex['location']
            if not location.startswith('/') and \
               not location.startswith('./'):
                locations.append(
                    os.path.join(
                        self.env.env['RESULTS'],
                        fileindex['location'] ) )
            else:
                locations.append(fileindex['location'])
        if len(locations) == 0:
            self.log.warning("**yields-files did not specify any files")
            self.log.warning("   No manifest will be produced")
            self.log.passed()
            return None

        if '__Csversion__' not in self.env.env:
            self.log.warning("There is no information to record into a manifest")
            self.log.passed()
            return None

        YAMLstring = yaml.safe_dump(self.env.env['__Csversion__'])
        for location in locations:
            with open(location, 'w') as manifest:
                manifest.write(YAMLstring)
        self.log.passed()
        return YAMLstring

