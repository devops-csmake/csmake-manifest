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
from datetime import datetime
import sys

class CsversionHLinuxConfigApt(CsmakeAspect):
    """Purpose: To capture the information provided to a HLinuxConfigApt
                section.
    Options: tag - Provides a context name for the information
                   for example - cs-mgmt-base-image or cs-mgmt-sources
    Joinpoints: end__build - captures the metadata from the section
    Creates Environment:
        __Csversion__ - A dictionary where product metadata is stored under
                        'product'.  'product' is product info keyed off of
                        the type of data stored, in this case 'apt'.
                        The same metadata/tag combination will be overwritten
                        if pulled twice.
                        The structure of the product dictionary is 
                        a dictionary of tags from builds with apt
                        { 'product' : { <tag> : { 'apt' : { <apt options>} } } }
        """

    REQUIRED_OPTIONS = ['tag']

    def end__build(self, phase, options, hlinuxsection, hlinuxoptions):
        if '__Csversion__' not in self.env.env:
            self.env.env['__Csversion__'] = {}
            self.log.debug("__Csversion__ not found creating new")
        if 'product' not in self.env.env['__Csversion__']:
            self.env.env['__Csversion__']['product'] = {}
            self.log.debug("product not found, creating new")
        versdict = self.env.env['__Csversion__']['product']
        if 'apt' not in versdict:
            versdict['apt'] = {}
            self.log.debug("build data not found, creating new")
        else:
            if options['tag'] in versdict['apt']:
                self.log.warning("apt, Tag: %s :: Overwriting %s",
                    options['tag'],
                    str(versdict['apt'][options['tag']]) )
        versdict['apt'][options['tag']] = dict(hlinuxoptions)
        self.log.passed()
        return True
