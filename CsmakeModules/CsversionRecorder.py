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
from Csmake.CsmakeModuleAllPhase import CsmakeModuleAllPhase
import pickle
import os.path
import os

class CsversionRecorder(CsmakeModuleAllPhase):
    """Purpose: Bridges the csversion information between phases
                and between builds if stashed and carried over.
                Merge order is: other-records - right updates left
                                file updates other-records
                                __Csversion__ updates last
    Options: file - location to read/merge and write the intermedate file
                    May be non-existant at execution.
             other-records - (OPTIONAL) locations of other records to merge
                             Can be defined with non-existant files.
                             Can be newline or comma delimited
    Phase: * - Does the merge and stash to intermediate file
           clean, clean_results, clean_build - Cleans the intermediate file
    Creates/Uses Environment:
        __Csversion__ - A dictionary where the keys are different types of
                        versioning information.  
                        Each value is a dictionary of dictionaries
                        where the structure of the sub-sub-dictionary
                        is controlled by the type of data that the
                        primary key defines to go in the entry.
                        For example, git source information would be:
                        env['__Csversion__']['sources'][<repo name>][<tag>]
                            ('git', {<git specific information>})
                        That is, the structure is:
                          <record type>
                              <record primary key>
                                  <record secondary key>
                                      <record info>
                        <record info> is considered to be unique,
                        and thus will be overwritten if the files referenced
                        and the current __Csversion__ state have overlapping 
                        copies of data represented by:
                           [<type>][<primary>][<secondary>]
        """

    REQUIRED_OPTIONS = ['file']

    def _updateRecords(self, resultDict, sourceDict):
        for key, value in sourceDict.items():
            if key not in resultDict:
                resultDict[key] = value
            else:
                for subkey, subvalue in value.items():
                    if subkey not in resultDict[key]:
                        resultDict[key][subkey] = subvalue
                    else:
                        resultDict[key][subkey].update(subvalue)

    def _consolidateVersionInfo(self, options):
        resultCsversion = {}
        otherRecordsFileList = []
        if 'other-records' in options and len(options['other-records']) > 0:
            otherRecordsFileList = ','.join(
                options['other-records'].split('\n')).split(',')
        otherRecordsFileList.append(options['file'])
        for other in otherRecordsFileList:
            other = other.strip()
            if os.path.exists(other):
                with open(other, 'rb') as pickledState:
                    self._updateRecords(
                        resultCsversion,
                        pickle.load(pickledState) )
        return resultCsversion

    def default(self, options):
        resultCsversion = self._consolidateVersionInfo(options)
        if '__Csversion__' in self.env.env:
            self._updateRecords(
                resultCsversion,
                self.env.env['__Csversion__'])
        else:
            self.log.info("No current __Csversion__ exists")
        self._ensureDirectoryExists(options['file'])
        with open(options['file'], 'wb') as pickledState:
            pickle.dump(resultCsversion, pickledState)
        self.env.env['__Csversion__'] = resultCsversion
        self.log.devdebug("Pickled __Csversion__ as: %s", str(resultCsversion))
        self.log.passed()
        return resultCsversion

    def clean(self, options):
        self._cleaningFiles()
        if os.path.exists(options['file']):
            os.remove(options['file'])
        try:
            self._cleanEnsuredDirectory(options['file'])
        except:
            self.log.exception("Could not clean directory for file: %s", options['file'])
        self.log.passed()
        return True

    def clean_results(self, options):
        return self.clean(options)

    def clean_build(self, options):
        return self.clean(options)
