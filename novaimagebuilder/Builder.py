# coding=utf-8

#   Copyright 2013 Red Hat, Inc.
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

import logging
from OSInfo import OSInfo
from StackEnvironment import StackEnvironment
from time import sleep


class Builder(object):
    def __init__(self, osid, install_location=None, install_type=None, install_script=None, install_config={}):
        """
        Builder selects the correct OS object to delegate build activity to.

        @param osid: The shortid for an OS record.
        @param install_location: The location of an ISO or install tree.
        @param install_type: The type of installation (iso or tree)
        @param install_script: A custom install script to be used instead of what OSInfo can generate
        @param install_config: A dict of various info that may be needed for the build.
                                (admin_pw, license_key, arch, disk_size, flavor, storage, name)
        """
        super(Builder, self).__init__()
        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))
        self.install_location = install_location
        self.install_type = install_type
        self.install_script = install_script
        self.install_config = install_config
        self.os = OSInfo().os_for_shortid(osid)
        self.os_delegate = self._delegate_for_os(self.os)
        self.env = StackEnvironment()

    def _delegate_for_os(self, os):
        """
        Select and instantiate the correct OS class for build delegation.

        @param os: The dictionary of OS info for a give OS shortid

        @return: An instance of an OS class that will control a VM for the image installation
        """
        # TODO: Change the way we select what class to instantiate to something that we do not have to touch
        # every time we add another OS class
        os_classes = {'fedora': 'RedHatOS', 'rhel': 'RedHatOS', 'win': 'WindowsOS', 'ubuntu': 'UbuntuOS'}
        os_classname = os_classes.get(os['distro'])

        if os_classname:
            try:
                os_module = __import__("novaimagebuilder." + os_classname, fromlist=[os_classname])
                os_class = getattr(os_module, os_classname)
                return os_class(osinfo_dict=self.os,
                                install_type=self.install_type,
                                install_media_location=self.install_location,
                                install_config=self.install_config,
                                install_script=self.install_script)
            except ImportError as e:
                self.log.exception(e)
                return None
        else:
            raise Exception("No delegate found for distro (%s)" % os['distro'])

    def run(self):
        """
        Starts the installation of an OS in an image via the appropriate OS class
        """
        self.os_delegate.prepare_install_instance()
        self.os_delegate.start_install_instance()

    def wait_for_completion(self, inactivity_timeout):
        """
        Waits for the install_instance to enter SHUTDOWN state then launches a snapshot

        @param inactivity_timeout amount of time to wait for activity before declaring the installation a failure in 10s of seconds (6 is 60 seconds)

        @return: image id or None
        """
        instance = self.os_delegate.install_instance
        if instance.shutoff(timeout=inactivity_timeout, in_progress=True):
            finished_image_id = instance.create_snapshot(self.install_config['name'] + '-jeos',
                    public=self.install_config['public'])
            instance.terminate()
            if self.os_delegate.iso_volume_delete:
                self.env.cinder.volumes.get(self.os_delegate.iso_volume).delete()
                self.log.debug("Deleted install ISO volume from cinder: %s" % self.os_delegate.iso_volume)
            return finished_image_id
        # Leave instance running if install did not finish. Exit with code 1.
        else:
            return None

    def abort(self):
        """
        Aborts the installation of an OS in an image.

        @return: Status of the installation.
        """
        self.os_delegate.abort()
        self.os_delegate.cleanup()
        return self.os_delegate.update_status()

    def status(self):
        """
        Returns the status of the installation.

        @return: Status of the installation.
        """
        # TODO: replace this with a background thread that watches the status and cleans up as needed.
        status = self.os_delegate.update_status()
        if status in ('COMPLETE', 'FAILED'):
            self.os_delegate.cleanup()
        return status
