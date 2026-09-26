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
import urllib.parse

class CsversionRecordGit(CsmakeAspect):
    """Purpose: Record the version of the git repos pulled using GitDependent 
    Options: tag - Provides a context name for the pull
                   for example - cs-mgmt-base-image or cs-mgmt-sources
    Joinpoints: passed__sources, passed__build, passed__pull
    Creates Environment:
        __Csversion__ - A dictionary where source versions are stored under
                        'sources'.  'sources' is version info keyed off of
                        the source repo name and a makefile designated tag.
                        The same repo/tag combination will be overwritten
                        if pulled twice (with a warning)
                        Every element in the 'sources' dictionary is 
                        a dictionary of tags contiaing a tuple:
                        (<repo-type>, <value-dict>) 
                        Git, specifically:
                        ('git', {'BRANCH':<reference>, 'REF':hashvalue}) 
    Note: Will use the result returned by GitDependent to record the SHA
          and will use the "ref" parameter to record the requested reference.
        """

    REQUIRED_OPTIONS = ['tag']

    def passed__sources(self, phase, options, gitsection, gitoptions):
        return self.passed__pull(phase, options, gitsection, gitoptions)

    def passed__pull(self, phase, options, gitsection, gitoptions):
        result, code, message = gitsection._getReturnValue(phase)
        if '__Csversion__' not in self.env.env:
            self.env.env['__Csversion__'] = {}
        if 'sources' not in self.env.env['__Csversion__']:
            self.env.env['__Csversion__']['sources'] = {}
        versdict = self.env.env['__Csversion__']['sources']
        if not result:
            self.log.error('GitDependent reported passed, but returned False')
            self.log.error('    %s: %s', code, message)
            self.log.failed()
            return False
        parsedurl = urllib.parse.urlparse(gitoptions['URL'])
        repo = parsedurl.path
        if repo[0] == '/':
            repo = repo[1:]
        branchparts = gitoptions['ref'].split(':')
        branch = branchparts[-1]
        entry = ('git', { 'BRANCH' : branch, 'REF' : result[1], 'URL' : gitoptions['URL'] })
        if repo not in versdict:
            versdict[repo] = {}
        else:
            if options['tag'] in versdict[repo]:
                self.log.warning("Repo: %s, Tag: %s :: Overwriting %s",
                    repo,
                    options['tag'],
                    str(versdict[repo][options['tag']] ))
        versdict[repo][options['tag']] = entry
        self.log.info("Repo: %s, Tag: %s :: Added %s",
            repo,
            options['tag'],
            str(versdict[repo][options['tag']] ))
        self.log.passed()
        return True
