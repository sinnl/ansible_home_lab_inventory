#!/usr/bin/env python3

from ansible.plugins.inventory import BaseInventoryPlugin
from ping3 import ping
from concurrent.futures import ThreadPoolExecutor
import netaddr
import time
import socket
import ipaddress
import sys
import json

ANSIBLE_METADATA = {
    'metadata_version': '1.0.0',
    'status': ['preview'],
    'supported_by': 'community'
}

DOCUMENTATION = '''
---
module: ansible_home_lab_inventory
plugin_type: inventory
short_description: Generetes inventory for AWX of hosts on local network.
version_added: ""
description:
    - "Scans network for hosts with ssh opened and existing DNS name."
options:
author:
    - "Lukasz D"
'''


class InventoryModule(BaseInventoryPlugin):
    """An example inventory plugin."""

    # VARS
    def __init__(self):
        self.ssh_port = 22
        self.cidr = '10.11.0.0/24'
        self.alive = []
        self.ssh_open = []
        self.inventory_groups = ['ungrouped', 'k8s_proxmox', 'k8s_pi', 'proxmox']

    NAME = 'sinnl.ansible_home_lab_inventory.scanner'

    def verify_file(self, path):
        """Verify that the source file can be processed correctly.

        Parameters:
            path:AnyStr The path to the file that needs to be verified

        Returns:
            bool True if the file is valid, else False
        """
        return True



    def check_cidr_format(self):
        """
        If provided subnet is not in correct CIDR notation exit with error.
        """
        try:
            cidr = ipaddress.ip_network(self.cidr)
        except:
            print(f'{red}{self.cidr} - is not valid CIDR notation for subnet.{reset}')
            sys.exit(1)

    def ping_check(self, addr):
        """
        helper method to test if system is reachable by ping
        """

        if ping(addr, timeout=2):
            self.alive.append(addr)

    def get_name(self, addr):
        try:
            hostname = socket.gethostbyaddr(addr)[0]
            return hostname
        except socket.herror:
            return False

    def port_check(self, addr):

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        socket.setdefaulttimeout(2)
        socket.timeout(2)


        result = sock.connect_ex((addr, self.ssh_port))
        if result == 0:
            hostname = self.get_name(addr)
            if hostname:
                self.ssh_open.append(hostname)

        sock.close()

    def add_metadata(self, hostvars):

        meta_dict = {'_meta': {'hostvars': {}}}

        for server, vars in hostvars.items():
            meta_dict['_meta']['hostvars'].update({server: {}})
            for key, value in vars.items():
                meta_dict['_meta']['hostvars'][server].update({key: value})

        return meta_dict

    def generate_inventory_dict(self, servers, hostvars):
        """
        Generates inventory dictionary that can be used and input for Anisble AWX
        """

        # Manually maintained groups
        # TO DO - consider moving outside of the function to global scope or external config file.
        # inventory_groups = ['ungrouped', 'k8s_proxmox', 'k8s_pi', 'proxmox']

        # Generate Initial dictionary with host variables based on the hostvars function input
        inventory_dict = self.add_metadata(hostvars)

        # Generate all roup with all children subgroups from inventory_groups
        inventory_dict['all'] = {'children': []}

        for group in self.inventory_groups:
            inventory_dict[group] = {'hosts': []}
            inventory_dict['all']['children'].append(group)

        # Populate groups based on hostname
        for server in servers:
            if 'proxmox' in server:
                inventory_dict['proxmox']['hosts'].append(server)
            elif 'k8s' in server:
                inventory_dict['k8s_proxmox']['hosts'].append(server)
            elif 'dude' in server or 'chief' in server:
                inventory_dict['k8s_pi']['hosts'].append(server)
            elif 'pfsense' not in server:
                inventory_dict['ungrouped']['hosts'].append(server)

        return inventory_dict

        """
        Example of the inventory_dict output. This is format required by Ansible AWX to import inventory correctly.
        {
            "_meta": {
                "hostvars": {
                    "web1.example.com": {
                        "ansible_user": "rdiscala"
                    },
                    "web2.example.com": {
                        "ansible_user": "rdiscala"
                    }
                }
            },
            "all": {
                "children": [
                    "ungrouped"
                ]
            },
            "ungrouped": {
                "hosts": [
                    "web1.example.com",
                    "web2.example.com"
                ]
            }
        }
        """

    def scan(self):
        ip_range = [ str(x) for x in netaddr.IPNetwork(self.cidr) ]


        with ThreadPoolExecutor() as executor:
            executor.map(self.ping_check, ip_range)


        with ThreadPoolExecutor() as executor:
            executor.map(self.port_check, self.alive)



    def generate_inventory(self):
        self.check_cidr_format()
        self.scan()
        hostvars = {
            'proxmox.itluk-home.eu': {
                'remote_user': 'opsadm'
            }
        }
        inventory = self.generate_inventory_dict(self.ssh_open, hostvars)

        return inventory

    def _get_raw_host_data(self):
        """Get the raw static data for the inventory hosts

        Returns:
            dict The host data formatted as expected for an Inventory Script
        """
        return {
            "all": {
                "hosts": ["web1.example.com", "web2.example.com"],
                "ungrouped": ["server1.example.com", "server2.example.com"]
            },
            "_meta": {
                "hostvars": {
                    "web1.example.com": {
                        "ansible_user": "rdiscala"
                    },
                    "web2.example.com": {
                        "ansible_user": "rdiscala"
                    }
                }
            }
        }

    def my_data(self):
        return {
            "_meta": {
                "hostvars": {
                    "proxmox.itluk-home.eu": {
                        "remote_user": "opsadm"
                    }
                }
            },
            # "all": {
            #     "children": [
            #         "ungrouped",
            #         "k8s_proxmox",
            #         "k8s_pi",
            #         "proxmox"
            #     ]
            # },
            "ungrouped": {
                "hosts": [
                    "itluk-website.itluk-home.eu",
                    "ansible.itluk-home.eu",
                    "postgres.itluk-home.eu",
                    "ha-proxy.itluk-home.eu"
                ]
            },
            "k8s_proxmox": {
                "hosts": [
                    "k8s-master.itluk-home.eu",
                    "k8s-node1.itluk-home.eu",
                    "k8s-node2.itluk-home.eu"
                ]
            },
            "k8s_pi": {
                "hosts": ["server1"]
            },
            "proxmox": {
                "hosts": [
                    "proxmox.itluk-home.eu"
                ]
            }
        }


    def parse(self, inventory, loader, path, cache=True):
        """Parse and populate the inventory with data about hosts.

        Parameters:
            inventory The inventory to populate
        """
        # The following invocation supports Python 2 in case we are
        # still relying on it. Use the more convenient, pure Python 3 syntax
        # if you don't need it.
        super(InventoryModule, self).parse(inventory, loader, path, cache)

        raw_inventory_data = self.generate_inventory()
        #raw_inventory_data = self._get_raw_host_data()
        #raw_inventory_data = self.my_data()

        _meta = raw_inventory_data.pop('_meta')
        for group_name, group_data in raw_inventory_data.items():
            print(group_name)
            self.inventory.add_group(group_name)
            if 'hosts' in group_data.keys():
                for host_name in group_data['hosts']:
                    self.inventory.add_host(host=host_name, group=group_name)
                    if host_name in _meta['hostvars'].keys():
                        for var_key, var_val in _meta['hostvars'][host_name].items():
                            self.inventory.set_variable(host_name, var_key, var_val)
