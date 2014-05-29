# encoding: utf-8

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
from CacheManager import CacheManager
from BaseOS import BaseOS
from OSInfo import OSInfo

class UbuntuOS(BaseOS):

    def __init__(self, osinfo_dict, install_type, install_media_location, install_config, install_script = None):
        super(UbuntuOS, self).__init__(osinfo_dict, install_type, install_media_location, install_config, install_script)

        # NOTE: (dkliban) We can't probe Nova to determine presence of direct boot 
        # so user must use --direct_boot option to take advantage of the  option

        if install_type == "iso" and not self.env.is_cdrom():
            raise Exception("ISO installs require a Nova environment that can \
                    support CDROM block device mapping")
        if not install_script:
            info = OSInfo()
            install_script_string = info.install_script(self.osinfo_dict['shortid'], self.install_config)
            install_script_string = install_script_string.replace('reboot','poweroff')
            if self.install_type == 'tree':
                install_script_string = install_script_string.replace('cdrom','')
                if self.install_media_location:
                    url = self.install_media_location
                else:
                    url = self.osinfo_dict['tree_list'][0].get_url()

                self.install_script = "url --url=%s\n%s" % (url,
                        install_script_string)
            else:
                self.install_script = install_script_string
            

    def prepare_install_instance(self):
        """ Method to prepare all necessary local and remote images for an
            install. This method may require significant local disk or CPU 
            resource.
        """
        
        self.cmdline = "append\
        preseed/url=http://169.254.169.254/latest/user-data\
        debian-installer/locale=en_US console-setup/layoutcode=us ipv6.disable=1\
        netcfg/choose_interface=auto keyboard-configuration/layoutcode=us\
        priority=critical --"

        #If direct boot option is available, prepare kernel and ramdisk
        if self.install_config['direct_boot']:
            if self.install_type == "iso":
                iso_locations = self.cache.retrieve_and_cache_object(
                        "install-iso", self, self.install_media_location, True)
                self.iso_volume = iso_locations['cinder']
                self.iso_aki = self.cache.retrieve_and_cache_object(
                        "install-iso-kernel", self, None, True)['glance']
                self.iso_ari = self.cache.retrieve_and_cache_object(
                        "install-iso-initrd", self, None, True)['glance']            
                self.log.debug ("Prepared cinder iso (%s), aki (%s) and ari \
                        (%s) for install instance" % (self.iso_volume, 
                            self.iso_aki, self.iso_ari))    
            if self.install_type == "tree":
                kernel_location = "%s%s" % (self.install_media_location,
                        self.url_content_dict()["install-url-kernel"])
                ramdisk_location = "%s%s" % (self.install_media_location, 
                        self.url_content_dict()["install-url-initrd"])
                self.tree_aki = self.cache.retrieve_and_cache_object(
                        "install-url-kernel", self, kernel_location, 
                        True)['glance']
                self.tree_ari = self.cache.retrieve_and_cache_object(
                        "install-url-initrd", self, ramdisk_location,
                        True)['glance']
                self.log.debug ("Prepared cinder aki (%s) and ari (%s) for \
                        install instance" % (self.tree_aki,
                            self.tree_ari))

        #Else, download kernel and ramdisk and prepare syslinux image with the two
        else:
            if self.install_type == "iso":
                iso_locations = self.cache.retrieve_and_cache_object(
                        "install-iso", self, self.install_media_location, True)
                self.iso_volume = iso_locations['cinder']
                self.iso_aki = self.cache.retrieve_and_cache_object(
                        "install-iso-kernel",  self, None, True)['local']
                self.iso_ari = self.cache.retrieve_and_cache_object(
                        "install-iso-initrd",  self, None, True)['local']
                self.boot_disk_id = self.syslinux.create_syslinux_stub(
                        "%s syslinux" % self.os_ver_arch(), self.cmdline, 
                        self.iso_aki, self.iso_ari)
                self.log.debug("Prepared syslinux image by extracting kernel \
                        and ramdisk from ISO")

            if self.install_type == "tree":
                kernel_location = "%s%s" % (self.install_media_location, 
                        self.url_content_dict()["install-url-kernel"])
                ramdisk_location = "%s%s" % (self.install_media_location, 
                        self.url_content_dict()["install-url-initrd"])
                self.url_aki = self.cache.retrieve_and_cache_object(
                        "install-url-kernel",  self, kernel_location, 
                        True)['local']
                self.url_ari = self.cache.retrieve_and_cache_object(
                        "install-url-initrd",  self, ramdisk_location, 
                        True)['local']
                self.boot_disk_id = self.syslinux.create_syslinux_stub(
                        "%s syslinux" % self.os_ver_arch(), self.cmdline, 
                        self.url_aki, self.url_ari)
                self.log.debug("Prepared syslinux image by extracting kernel \
                        and ramdisk from ISO")


    def start_install_instance(self):
        if self.install_config['direct_boot']:
            self.log.debug("Launching direct boot ISO install instance")
            if self.install_type == "iso":
                self.install_instance = self.env.launch_instance(
                        root_disk=('blank', 10), 
                        install_iso=('cinder', self.iso_volume),
                        aki=self.iso_aki, ari=self.iso_ari, 
                        cmdline=self.cmdline, userdata=self.install_script,
                        direct_boot=True)

            if self.install_type == "tree":
                self.install_instance = self.env.launch_instance(
                        root_disk=('blank', 10), aki=self.tree_aki,
                        ari=self.tree_ari, cmdline=self.cmdline,
                        userdata=self.install_script, direct_boot=True)

        else:
            if self.install_type == "tree":
                self.log.debug("Launching syslinux install instance")
                self.install_instance = self.env.launch_instance(root_disk=(
                    'glance', self.boot_disk_id), userdata=self.install_script)

            if self.install_type == "iso":
                self.install_instance = self.env.launch_instance(root_disk=(
                    'glance', self.boot_disk_id), install_iso=('cinder',
                        self.iso_volume), userdata=self.install_script)

    def update_status(self):
        return "RUNNING"

    def wants_iso_content(self):
        return True

    def iso_content_dict(self):
        return { "install-iso-kernel":
                 "/install/vmlinuz",
                 "install-iso-initrd":
                 "/install/initrd.gz"}

    def url_content_dict(self, architecture='x86_64'):
        if architecture is 'x86':
            return { "install-url-kernel":
                     "main/installer-i386/current/images/netboot/ubuntu-installer/i386/linux",
                     "install-url-initrd":
                     "main/installer-i386/current/images/netboot/ubuntu-installer/i386/initrd.gz"}
        else:
            return { "install-url-kernel":
                     "main/installer-amd64/current/images/netboot/ubuntu-installer/amd64/linux",
                     "install-url-initrd":
                     "main/installer-amd64/current/images/netboot/ubuntu-installer/amd64/initrd.gz"}

    def abort(self):
        pass

    def cleanup(self):
        pass
