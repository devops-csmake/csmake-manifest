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
import urllib.parse
import git
import os.path

class CsversionRecordThisGit(CsmakeModule):
    """Purpose: Record the version of the referred local git repo according to
                'repopath'
    Options: tag - Provides a context name for the pull
                   for example - cs-mgmt-base-image or cs-mgmt-sources
             repopath - point to the repo in the build to get information on
             pass-non-repos - (OPTIONAL) When set to True - this section will
                              still pass if there is no repo at 'repopath'
    Phases: sources, pull, build - will record the current git version
                                   in __Csversion__
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
                        ('git', {'BRANCH':<reference>, 'REF':hashvalue,
                            'URL':<url>, 'SUBMODULES':[<submodules>]})
                        The submodules entry is optional.  When it is
                        present, it contains a list of dictionaries containing
                        {'URL':<url>, 'PATH':<path in outer repo>,
                            'REF':hashvalue}.
    Note: Will use the result returned by GitDependent to record the SHA
          and will use the "ref" parameter to record the requested reference.
        """

    REQUIRED_OPTIONS = ['tag', 'repopath']

    def default(self, options):
        if '__Csversion__' not in self.env.env:
            self.env.env['__Csversion__'] = {}
        self.log.passed()

    def sources(self, options):
        return self.pull(options)

    def build(self, options):
        return self.pull(options)

    def pull(self, options):
        if '__Csversion__' not in self.env.env:
            self.env.env['__Csversion__'] = {}
        if 'sources' not in self.env.env['__Csversion__']:
            self.env.env['__Csversion__']['sources'] = {}
        versdict = self.env.env['__Csversion__']['sources']

        if 'pass-non-repo' in options and options['pass-non-repo'] == 'True':
            if not os.path.exists(os.path.join(
                options['repopath'],
                '.git') ):
                self.log.info("There is no repo at '%s'.  Passing because pass-non-repo is set", options['repopath'])
                self.log.passed()
                return True

        gitrepo = None
        try:
            gitrepo = git.Repo(os.path.realpath(options['repopath']))
        except:
            self.log.exception("Couldn't find a vaild git repo on %s", 'repopath')
            self.log.error()
            return False

        reponame = "(local) %s" % os.path.split(
            os.path.abspath(
                options['repopath']) )[1]
        sha = gitrepo.commit().hexsha
        remoteref = None
        remote = None
        active = None
        try:
            active = gitrepo.active_branch
        except TypeError:
            self.log.info(
                "git repo '%s' isn't attached to a branch",
                options['repopath'] )
        try:
            remoteref = active.tracking_branch()
            remote = gitrepo.remotes[remoteref.remote_name]
        except (IndexError, TypeError, AttributeError, ValueError):
            self.log.info(
                "git repo '%s' isn't tracking a remote branch",
                options['repopath'] )
            self.log.info(" - proceeding to read git's mind")
            remoteref = None
            remote = None
            for current in gitrepo.remotes:
                for ref in current.refs:
                    if not ref.is_remote():
                        continue
                    if str(ref).endswith("HEAD"):
                        continue
                    if gitrepo.commit().hexsha == ref.commit.hexsha:
                        remote = current
                        remoteref = ref
                        #We'll take any remote reference, but...
                        #We really only want a head ref - if we found one bail
                        if issubclass(type(ref), git.refs.head.Head):
                            break

        if remoteref is None or remote is None:
            self.log.info("git repo %s isn't tracking a remote - local info will be used")
            reponame = os.path.split(
                os.path.abspath(options['repopath']) )[1]
            url = "(local) %s" % reponame
            branchname = '(detached)'
            if active is not None:
                branchname = str(active)
            branch = "(local) %s" % branchname
        else:
            url = remote.url
            reponame = urllib.parse.urlparse(url).path
            branch = str(remoteref)
            branch = '/'.join(branch.split('/')[1:])

        if reponame[0] == '/':
            reponame = reponame[1:]
        entry = ('git', { 'BRANCH' : branch, 'REF' : gitrepo.commit().hexsha, 'URL' : url })
        if reponame not in versdict:
            versdict[reponame] = {}
        else:
            if options['tag'] in versdict[reponame]:
                self.log.warning("Repo: %s, Tag: %s :: Overwriting %s",
                    reponame,
                    options['tag'],
                    str(versdict[reponame][options['tag']] ))

        # Add submodule information, if any
        if len(gitrepo.submodules) >= 1:
            entry[1]['SUBMODULES'] = submodule_list = []
            for submodule in gitrepo.submodules:
                current_submodule = {'URL': submodule.url, 'PATH': submodule.path, 'REF': submodule.hexsha}
                submodule_list.append(current_submodule)


        versdict[reponame][options['tag']] = entry
        self.log.info("Repo: %s, Tag: %s :: Added %s",
            reponame,
            options['tag'],
            str(versdict[reponame][options['tag']] ))
        self.log.passed()
        return True
