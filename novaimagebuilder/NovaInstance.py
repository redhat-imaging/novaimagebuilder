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
from time import sleep

class NovaInstance:

    def __init__(self, instance, stack_env):
        self.log = logging.getLogger('%s.%s' % (__name__, self.__class__.__name__))
        self.last_disk_activity = 0
        self.last_net_activity = 0
        self.instance = instance
        self.stack_env = stack_env
        self.floating_ips = []
    
    @property
    def id(self):
        """


        @return:
        """
        return self.instance.id

    @property
    def status(self):
        """


        @return:
        """
        self.instance = self.stack_env.nova.servers.get(self.instance.id)
        return self.instance.status

    def get_disk_and_net_activity(self):
        """


        @return:
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

        @param inactivity_timeout:
        @return:
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

        @return: floating_ip: A new floating IP object from Nova.
        """
        new_ip = self.stack_env.nova.floating_ips.create()
        self.instance.add_floating_ip(new_ip)
        self.floating_ips.append(new_ip)
        return new_ip

    def remove_floating_ip(self, ip_addr):
        """
        Remove a floating IP address from the instance.

        @param ip_addr: floating_ip: The floating IP object to remove.
        """
        self.floating_ips.remove(ip_addr)
        self.instance.remove_floating_ip(ip_addr)
        self.stack_env.nova.floating_ips.delete(ip_addr)