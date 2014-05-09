#   Copyright 2011 Red Hat, Inc.
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

from distutils.core import setup
from distutils.command.sdist import sdist as _sdist
import subprocess
import time

VERSION = '0.0.1'
RELEASE = '0'

class sdist(_sdist):
    """ custom sdist command, to prep nova-image-builder.spec file """

    def run(self):
        global VERSION
        global RELEASE

        # Create a development release string for later use
        git_head = subprocess.Popen("git log -1 --pretty=format:%h",
                                    shell=True,
                                    stdout=subprocess.PIPE).communicate()[0].strip()
        date = time.strftime("%Y%m%d%H%M%S", time.gmtime())
        git_release = "%sgit%s" % (date, git_head)

        # Expand macros in imagefactory.spec.in
        spec_in = open('nova-image-builder.spec.in', 'r')
        spec = open('nova-image-builder.spec', 'w')
        for line in spec_in.xreadlines():
            if "@VERSION@" in line:
                line = line.replace("@VERSION@", VERSION)
            elif "@RELEASE@" in line:
                # If development release, include date+githash in %{release}
                if RELEASE.startswith('0'):
                    RELEASE += '.' + git_release
                line = line.replace("@RELEASE@", RELEASE)
            spec.write(line)
        spec_in.close()
        spec.close()

        # Create Version.py to allow internal version repording via the API
        version_out = open("novaimagebuilder/Version.py", 'w')
        version_out.write('VERSION = "%s-%s"\n' % (VERSION, RELEASE))
        version_out.close()

        # Run parent constructor
        _sdist.run(self)

# datafiles=[('/etc/imagefactory', ['imagefactory.conf']) ]
# Not needed for now but leaving this in as a reminder of how the structure works
datafiles = None

setup(name='nova-image-builder',
      version=VERSION,
      description='Tool to build OS images from scratch in OpenStack Nova',
      author='Ian McLeod',
      author_email='imcleod@redhat.com',
      license='Apache License, Version 2.0',
      url='https://github.com/redhat-imaging/novaimagebuilder',
      packages=['novaimagebuilder'],
      scripts=['nova-install'],
      data_files = datafiles,
      cmdclass = {'sdist': sdist}
      )
