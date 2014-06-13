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
import os
from time import sleep


class NovaInstance(object):
    """
    A wrapper class for server objects in OpenStack Nova.

    @param instance: The OpenStack Nova server to wrap.
    @param stack_env: An instance of novaimagebuilder.StackEnvironment to use for communication with OpenStack
    """

    def __init__(self, instance, stack_env, key_pair=None):
        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))
        self.last_disk_activity = 0
        self.last_net_activity = 0
        self._instance = instance
        self.stack_env = stack_env
        self.floating_ips = []
        self.key_pair = key_pair
        self.key_dir = os.path.expanduser('~/') + '.ssh/'

        if self.key_pair:
            if not os.path.exists(self.key_dir):
                os.mkdir(self.key_dir, mode=600)
            private_key_file = open(self.key_dir + key_pair.name, 'w')
            os.fchmod(private_key_file.fileno(), 0600)
            private_key_file.write(key_pair.private_key)
            private_key_file.close()
            public_key_file = open(self.key_dir + key_pair.name + '.pub', 'w')
            os.fchmod(public_key_file.fileno(), 0600)
            public_key_file.write(key_pair.public_key)
            public_key_file.close()

    @property
    def instance(self):
        """
        The instance, fetched from nova.

        @return: Instance from nova.
        """
        self._instance = self.stack_env.nova.servers.get(self._instance.id)
        return self._instance

    @property
    def id(self):
        """
        The nova server id of the instance.

        @return: id string from nova
        """
        return self._instance.id

    @property
    def status(self):
        """
        The nova server status of the instance.

        @return: status string from nova
        """
        return self.instance.status

    def get_disk_and_net_activity(self):
        """
        Returns a total count for each of disk and network activity.

        @return: disk_activity int, net_activity int
        """
        disk_activity = 0
        net_activity = 0
        diagnostics = self._instance.diagnostics()[1]
        if not diagnostics:
            return 0, 0
        for key, value in diagnostics.items():
            if ('read' in key) or ('write' in key):
                disk_activity += int(value)
            if ('rx' in key) or ('tx' in key):
                net_activity += int(value)
        return disk_activity, net_activity

    def is_active(self):
        """
        Determines if server instance is working or hung on an error based on disk and network activity.

        @return: boolean
        """
        self.log.debug("checking for inactivity")
        try:
            current_disk_activity, current_net_activity = self.get_disk_and_net_activity()
        except Exception, e:
            saved_exception = e
            # Since we can't get disk and net activity we assume
            # instance is not active (usually before instance finished 
            # spawning.
            return False
        self.log.debug("Disk activity: %s" % current_disk_activity)
        self.log.debug("Network activity: %s" % current_net_activity)
        if (current_disk_activity == self.last_disk_activity) and \
                (current_net_activity < (self.last_net_activity + 4096)):
            # if we saw no read or write requests since the last iteration
            self.last_net_activity = current_net_activity
            return False
        else:
            # if we did see some activity, record it
            self.last_disk_activity = current_disk_activity
            self.last_net_activity = current_net_activity
            return True

    def add_floating_ip(self):
        """
        Add a floating IP address to the instance.

        @return: floating_ip: A new FloatingIP object from Nova.
        """
        new_ip = self.stack_env.nova.floating_ips.create()
        self._instance.add_floating_ip(new_ip)
        self.floating_ips.append(new_ip)
        return new_ip

    def remove_floating_ip(self, ip_addr):
        """
        Remove a floating IP address from the instance.

        @param ip_addr: The FloatingIP object to remove.
        """
        self.floating_ips.remove(ip_addr)
        self._instance.remove_floating_ip(ip_addr)
        self.stack_env.nova.floating_ips.delete(ip_addr)

    def shutoff(self, timeout=180, in_progress=False):
        """
        Stop the instance in Nova.

        @param timeout: Number of seconds to wait before giving up
        @param in_progress: boolean If set to True, shutoff will only monitor the instance for SHUTOFF state instead of
         initiating the shutdown. (Default: False)
        @return: boolean
        """
        if not in_progress:
            self._instance.stop()

        _timeout = timeout
        count = 1200
        for index in range(count):
            _status = self.status
            if _status == 'SHUTOFF':
                self.log.debug('Instance (%s) has entered SHUTOFF state' % self.id)
                return True
            if index % 10 == 0:
                self.log.debug('Waiting for instance status SHUTOFF - current status (%s): %d/%d' % (_status, index, count))
            if not self.is_active():
                _timeout -= 1
            else:
                _timeout = timeout
            if _timeout == 0:
                self.log.debug('Instance has become inactive but running. Please investigate the actual nova instance.')
                return False
            sleep(1)

    def terminate(self):
        """
        Stop and delete the instance from Nova.

        """
        _id = self.id
        self._instance.delete()
        self.log.debug('Waiting for instance (%s) to be terminated.' % _id)

        try:
            while self.instance:
                self.log.debug('Nova instance %s has status %s...' % (_id, self.status))
                sleep(5)
        except:
            self.log.debug('Nova instance %s deleted.' % _id)

            if self.key_pair:
                self.log.debug('Removing key pair: %s' % self.key_pair.name)

                key_dir = os.path.expanduser('~/') + '.ssh/'
                try:
                    self.stack_env.nova.keypairs.delete(self.key_pair)
                    os.remove(key_dir + self.key_pair.name)
                    os.remove(key_dir + self.key_pair.name + '.pub')
                except:
                    self.log.exception('Unable to remove key pair %s%s' % (key_dir, self.key_pair.name))

    def create_snapshot(self, image_name, with_properties=None, strip_direct_boot=True):
        """
        Create a snapshot image based on this Nova instance.

        @param image_name: str Name of the new image snapshot.
        @param with_properties: dict Optional metadata that should be added to the snapshot image.
        @param strip_direct_boot: boolean Should direct boot parameters be stripped if present? (Default: True)
        @raise Exception: When the snapshot reaches 'error' instead of 'active' status.
        @return Glance id of the snapshot image
        """
        snapshot_id = self._instance.create_image(image_name)
        self.log.debug('Waiting for glance image id (%s) to become active' % snapshot_id)
        snapshot = self.stack_env.glance.images.get(snapshot_id)
        while snapshot:
            self.log.debug('Current image status: %s' % snapshot.status)
            if snapshot.status == 'error':
                raise Exception('Image entered error status while waiting for completion')
            elif snapshot.status == 'active':
                self.log.debug('Glance image id (%s) is now active' % snapshot_id)
                break
            sleep(2)
            snapshot = self.stack_env.glance.images.get(snapshot_id)

        if with_properties or strip_direct_boot:
            snapshot_properties = snapshot.properties
            if strip_direct_boot:
                for key in ('kernel_id', 'ramdisk_id', 'command_line'):
                    if key in snapshot_properties:
                        del snapshot_properties[key]
                metadata = {'properties': snapshot_properties}
                snapshot.update(**metadata)
            if isinstance(with_properties, dict):
                snapshot.update(**with_properties)

        sleep(10)  # Give nova a chance to see the image is active

        return snapshot_id
