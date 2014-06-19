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

    def __init__(self, instance, stack_env, key_pair=None, floating_ip=False):
        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))
        self.last_disk_activity = 0
        self.last_net_activity = 0
        self._instance = instance
        self.stack_env = stack_env
        self.floating_ips = []
        self.key_pair = key_pair
        self.key_dir = os.path.expanduser('~/') + '.ssh/'
        self.security_group = None

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

        if floating_ip :
            # Wait for the instance to be active before assigning floaiting ip
            for index in range(1, 120, 5):
                status = self.stack_env.nova.servers.get(instance.id).status
                if status == 'ACTIVE':
                    self.add_floating_ip()
                    return
                elif status == 'ERROR':
                    self.log.debug('Instance (%s: %s) has status %s.' % (instance.name, instance.id, instance.status))
                    return
                else:
                    self.log.debug('Waiting for instance (%s) to become active...' % instance.name)
                    sleep(5)

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
        diagnostics = self.instance.diagnostics()[1]
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
            # Since we can't get disk and net activity we assume
            # instance is not active (usually before instance finished 
            # spawning.
            self.log.debug('Caught exception while polling for disk and network activity: %s' % e)
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

        try:
            self.get_disk_and_net_activity()
            _timeout = timeout
        except Exception as e:
            self.log.debug('Unable to check for disk and network activity. Setting timeout to 1 hour. %s' % e)
            _timeout = 216000

        index = 0
        while(True):
            _status = self.status
            if _status == 'SHUTOFF':
                self.log.debug('Instance (%s) has entered SHUTOFF state' % self.id)
                return True
            if index % 10 == 0:
                self.log.debug(
                    'Waiting for instance status SHUTOFF')
            if not self.is_active():
                _timeout -= 1
            else:
                _timeout = timeout
            if _timeout == 0:
                self.log.debug('Instance has become inactive but running. Please investigate the actual nova instance.')
                return False
            index += 1
            sleep(1)

    def terminate(self):
        """
        Stop and delete the instance from Nova.

        """
        ips_to_remove = self.floating_ips[:]
        for ip in ips_to_remove:
            self.remove_floating_ip(ip)
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

    def create_snapshot(self, image_name, with_properties=None, public=False):
        """
        Create a snapshot image based on this Nova instance.

        @param image_name: str Name of the new image snapshot.
        @param with_properties: dict Optional metadata that should be added to the snapshot image.
        @param public: boolean Should the snapshot be public, default False 
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
        metadata = {'is_public': public}
        if isinstance(with_properties, dict):
            metadata['properties'] = with_properties
        else:
            metadata['properties'] = {}
        snapshot.update(**metadata)
        # TODO: (dkliban) Remove the sleep statement when 
        # https://bugs.launchpad.net/nova/+bug/1329882 is fixed
        sleep(10)  # Give nova a chance to see the image is active

        return snapshot_id

    def open_ssh(self):
        """
        Creates a security group with a rule to allow ssh access.

        @return: True or False
        """
        try:
            nova = self.stack_env.nova
            self.security_group = nova.security_groups.create('NovaImageBuilder-%s' % self.id,
                                                              'Access to services needed by NovaImageBuilder')
            self.log.debug('Security group (id=%s, name=%s created.' % (self.security_group.id,
                                                                        self.security_group.name))
            rule = nova.security_group_rules.create(self.security_group.id, 'tcp', 22, 22)
            self.log.debug('Rule created: %s' % str(rule.to_dict()))
            nova.servers.add_security_group(self.id, self.security_group.name)
            self.log.debug('Added security group %s and added to instance %s' % (self.security_group.name, self.id))
            return True
        except Exception as e:
            self.log.debug('Failed to add security group %s to %s: %s' % (self.security_group.name, self.id, e))
            return False

    def close_ssh(self):
        """
        Removes the security group.

        """
        self.stack_env.nova.servers.remove_security_group(self.id, self.security_group.name)
        self.stack_env.nova.security_groups.delete(self.security_group)
        self.security_group = None
