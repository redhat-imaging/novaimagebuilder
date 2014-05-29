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

You can either source your keystonerc file or manually set your OpenStack environment variables.

To try it out install the requirements listed below then run commands like this:

You can either source your keystonerc file or provide your OpenStack environment variables
on command line.

#### Sample keystone.rc

    export OS_TENANT_NAME=admin;export OS_USERNAME=admin;export OS_PASSWORD=admin;
    export OS_AUTH_URL=http://10.10.10.10:5000/v2.0/;export OS_AUTH_STRATEGY=keystone

#### Optional arguments

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

## Folsom and Havana 
#### Create a Fedora 19 JEOS image in glance using a network install

    ./nova-install --name fedora19-image --os fedora19 --install_tree http://mirrors.kernel.org/fedora/releases/19/Fedora/x86_64/os/ --install_script ./fedora19.ks

#### Create a Fedora 19 JEOS image in glance using an ISO

    ./nova-install --name fedora19-syslinux-from-dvd --os fedora19 --install_iso http://mirrors.kernel.org/fedora/releases/19/Fedora/x86_64/iso/Fedora-19-x86_64-DVD.iso --install_script ./fedora19-DVD.ks

#### Create an Ubuntu 12.04 image in glance using a network install

    ./nova-install --name ubuntu-demo-image --os ubuntu12.04 --install_tree http://us.archive.ubuntu.com/ubuntu/dists/precise/ --install_script ./ubuntu12.04.preseed

#### Create an Ubuntu 12.04 image in glance using an ISO

    ./nova-install --name ubuntu-syslinux-from-dvd --os ubuntu12.04 --install_iso http://mirrors.xmission.com/ubuntu-cd/12.04/ubuntu-12.04.4-server-amd64.iso --install_script ./ubuntu12.04.preseed


## Icehouse
#### Create a Fedora 19 JEOS image in glance using a network install

    ./nova-install --direct_boot --name fedora19-image --os fedora19 --install_tree http://download.devel.redhat.com/released/F-19/GOLD/Fedora/x86_64/os/ --install_script ./fedora19.ks

#### Create a Fedora 19 JEOS image in glance using an ISO

    ./nova-install --direct_boot --name fedora19-syslinux-from-dvd --os fedora19 --install_iso ihttp://mirrors.kernel.org/fedora/releases/19/Fedora/x86_64/iso/Fedora-19-x86_64-DVD.iso --install_script ./fedora19-DVD.ks

#### Create an Ubuntu 12.04 image in glance using a network install

    ./nova-install --direct_boot --name ubuntu-demo-image --os ubuntu12.04 --install_tree http://us.archive.ubuntu.com/ubuntu/dists/precise/ --install_script ./ubuntu12.04.preseed

#### Create an Ubuntu 12.04 image in glance using an ISO

    ./nova-install --direct_boot --name ubuntu-from-dvd --os ubuntu12.04 --install_iso http://mirrors.xmission.com/ubuntu-cd/12.04/ubuntu-12.04.4-server-amd64.iso --install_script ./ubuntu12.04.preseed



## What does this do?

The commands executed against Folsom and Havana OpenStack releases generate
a small syslinux-based bootable image that is used to start unattended Anaconda
or Ubuntu installations.  It contains only the initrd and vmlinuz from the
install source and a syslinux.cfg file. The installer then writes over this
minimal image.

The kickstart/preseed files are passed to the installers via OpenStack 
user-data and the appropriate kernel command line parameters in the 
syslinux configuration file.

The tool uploads this bootstrapping image to glance, launches it, and
waits for it to shut down.  If shutdown occurs within the timeout period
we assume that the installer has finished and take a snapshot of the current
instance state, which is the completed install.

You can monitor progress via the Horizon dashboard.  The console should display
an automated install happening.

Icehouse release added the ability to specify the kernel command line as a
property of a glance image.  So when --directi\_boot parameter is specified,
three images are uploaded into Glance: initrd, vlinuz, and a blank qcow2 image.
The blank image has 3 extra properties: ramdisk\_id, kernel\_id,
and os\_command\_line.  An instance is then started using the blank image.  Once
the instance boots, it starts the automated install.  

### What operating systems can it support?

Fedora 17, Fedora 18, Fedora 19, Fedora 20. 

RHEL 6.5, RHEL 6.4, RHEL 5.9

Ubuntu 12.10, 12.04 and 10.04

This approach should work as far back as Fedora 10 and RHEL 4 U8 and on
other Linux variants including SLES.


### ISO Install Media

When --install\_iso parameter is present, the tool downloads the ISO, extracts
the kernel and ramdisk and then uploads the ISO to Cinder while ramdisk and
kernel are uploaded to Glance.
Once an instance is started the ISO volume is attached as a CDROM to the
instance.  For Fedora and RHEL, the kickstart file needs to specify that
install should take place from cdrom.  Ubuntu installer seems to recognize this
without any changes to preseed file.

### Requirements

This script has been tested with the following OpenStack client packages:

* python-glanceclient
* python-novaclient
* python-keystoneclient
* python-cinderclient
* python-libguestfs
* syslinux
* qemu-img

### TODO

Add sample kickstart and preseed files

Add instructions on how to do Windows image builds
