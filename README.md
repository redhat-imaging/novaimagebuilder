Building OS images in NOVA
==========================

This is a new image building approach for OpenStack.

It is a command line tool that builds working OpenStack images by
running Anaconda or other native installers within Nova.  In its simplest form 
it requires only a kickstart or preseed file as input.  All of the heavy lifting
is done inside of OpenStack instances.

Early discussion of this approach can be found here:

https://wiki.openstack.org/wiki/NovaImageBuilding

It has been developed and tested on RHEL6 against Folsom, Havana and Icehouse OpenStack
releases.  However, it should work with newer host OSes and newer OpenStack releases.

To try it out install the requirements listed below then run commands like this:

You can either source your keystonerc file or provide your OpenStack environment variables
on command line.

Sample keystone.rc:

    export OS_TENANT_NAME=admin;export OS_USERNAME=admin;export OS_PASSWORD=admin;
    export OS_AUTH_URL=http://10.10.10.10:5000/v2.0/;export OS_AUTH_STRATEGY=keystone

optional arguments:

    -h, --help            show this help message and exit
    --os OS               The shortid of an OS. Required for both installation
                          types.
    --os_list             Show the OS list available for image building.
    --install_iso INSTALL_ISO
                          Location of the installation media ISO.
    --install_tree INSTALL_TREE
                          Location of an installation file tree.
    --install_script INSTALL_SCRIPT
                          Custom install script file to use instead of
                          generating one.
    --admin_pw ADMIN_PW   The password to set for the admin user in the image.
    --license_key LICENSE_KEY
                          License/product key to use if needed.
    --arch ARCH           The architecture the image is built for. (default:
                          x86_64)
    --disk_size DISK_SIZE
                          Size of the image root disk in gigabytes. (default:
                          10)
    --instance_flavor INSTANCE_FLAVOR
                          The type of instance to use for building the image.
                          (default: vanilla)
    --name NAME           A name to assign to the built image.
    --image_storage {glance,cinder,both}
                          Where to store the final image: glance, cinder, both
                          (default: glance)
    --debug               Print debugging output to the logfile. (default:
                          False)
    --direct_boot         Provide kernel command line at launch of instance.
                          Instead of building a syslinux image. (default: False)

#### Create a Fedora 18 JEOS image in glance using a network install

    ./nova-install --name fedora19-image --os fedora19 --install_tree http://download.devel.redhat.com/released/F-19/GOLD/Fedora/x86_64/os/ --install_script ./fedora19.ks

#### Create an Ubuntu 12.04 image in glance using a network install

    ./nova-install --name ubuntu-demo-image --os ubuntu12.04 --install_tree http://us.archive.ubuntu.com/ubuntu/dists/precise/ --install_script ./ubuntu12.04.preseed

#### Create a Fedora 18 JEOS image as a volume snapshot using a network install

    ./nova-install --username admin --tenant admin --password password --auth-url http://10.10.10.10:5000/v2.0 \
                      --glance-url http://10.10.10.10:9292/ --root-password myrootpw --create-volume \
                        install_scripts/fedora-18-jeos.ks
    ./nova-install --image_storage cinder --name fedora19-image --os fedora19 --install_tree http://download.devel.redhat.com/released/F-19/GOLD/Fedora/x86_64/os/ --install_script ./fedora19.ks

#### Create a Fedora 18 JEOS image as a volume snapshot using an install DVD pulled from a Fedora mirror

     ./nova-install --name fedora18-image --os fedora18 --install_iso http://mirror.pnl.gov/fedora/linux/releases/18/Fedora/x86_64/iso/Fedora-18-x86_64-DVD.iso --install_script ./fedora18-DVD.ks

#### Create a Fedora 18 JEOS image as a volume snapshot by re-using the DVD volume snapshot created above

    ./nova-install --username admin --tenant admin --password password --auth-url http://10.10.10.10:5000/v2.0 \
                      --create-volume --install-media-snapshot <SNAPSHOT_ID_REPORTED_ABOVE> \
                      --install-tree-url \
                        http://mirror.pnl.gov/fedora/linux/releases/18/Fedora/x86_64/os/ \
                      --glance-url http://10.10.10.10:9292/ --root-password myrootpw install_scripts/fedora-18-jeos-DVD.ks


### What does this do?

The script generates a small syslinux-based bootable image that is used
to start unattended Anaconda or Ubuntu installations.  It contains only 
the initrd and vmlinuz from the install source and a syslinux.cfg file.
The installer then writes over this minimal image.

The kickstart/preseed files are passed to the installers via OpenStack 
user-data and the appropriate kernel command line parameters in the 
syslinux configuration file.

The script uploads this bootstrapping image to glance, launches it, and
waits for it to shut down.  If shutdown occurs within the timeout period
we assume that the installer has finished and take a snapshot of the current
instance state, which is the completed install.

You can monitor progress via Anaconda's VNC support, which is enabled
in the example kickstarts under the "install_scripts" directory. The 
script reports the instance IP and gives the exact invocation of 
vncviewer that is needed to connect to the install.

You can do something similar with an Ubuntu install using an SSH console.
However, this feature stops the installation and waits for user input so
it is commented out in the example preseed files.  See instructions in
the comments for how to enable this.


### What operating systems can it support?

The install_scripts contains known-working kickstart and preseed files for:

Fedora 18, Fedora 17, RHEL 6.4, RHEL 5.9

Ubuntu 12.10, 12.04 and 10.04

This approach should work as far back as Fedora 10 and RHEL 4 U8 and on
other Linux variants including SLES.


### Volume Based Images

By default the script will build a Glance backed image.  If passed the
--create-volume option it will instead build a volume backed "snapshot"
image.


### ISO Install Media

It also contains initial support for presenting installer ISO images as
a source for installation packages.  This support has only been tested for
Fedora 18 for the moment.  It is somewhat limited because OpenStack currently
only allows these images to be mapped into the instance as "normal"
block devices, rather than CDROMs.  Not all installers can deal with this.

(Note: When using the install media volume feature you must still pass
a "--install-tree-url" option as demonstrated in the examples above.  This
is necessary to allow the script to retrieve the install kernel and ramdisk
without having to pull down a copy of the entire ISO.)

### Requirements

This script has been tested with the following OpenStack client packages:

* python-glanceclient-0.5.1-1.el6.noarch
* python-novaclient-2.10.0-2.el6.noarch
* python-keystoneclient-0.1.3.27-1.el6.noarch
* python-cinderclient-0.2.26-1.el6.noarch

Newer and older versions may work.

It also requires:

* python-libguestfs
* syslinux
* qemu-img

If you want to view ongoing installs over VNC you will need:

* tigervnc


### TODO

Better documentation

Better error detection and reporting

Support for more operating systems.

Support for sourcing install scripts through libosinfo

Support for enhanced block device mapping when it becomes available

Support for direct booting of kernel/ramdisk/cmdline combinations when/if it is added to Nova

Improved detection of install success or failure

Support for caching of self-install images
