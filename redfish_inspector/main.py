#!python3

import argparse
import json
import logging
import sys
from pathlib import Path
from textwrap import indent
from typing import List, Mapping
import re


import concurrent.futures
from typing_extensions import final

import openstack
import sushy
from openstack.baremetal.v1.node import Node
from openstack.baremetal.v1.port import Port
from openstack.cloud import exc
from sushy import utils
from sushy.main import Sushy
from sushy.resources.chassis.chassis import Chassis
from sushy.resources.system.ethernet_interface import (
    EthernetInterface,
    EthernetInterfaceCollection,
)
from sushy.resources.system.processor import Processor
from sushy.resources.system.storage.storage import Storage
from sushy.resources.system.storage.drive import Drive
from sushy.resources.system.system import System
from sushy.exceptions import ConnectionError, AccessError
from sushy.resources import base, common, constants

# from urllib3.exceptions import InsecureRequestWarning

# Initialize and turn on debug logging
openstack.enable_logging(debug=False)
logging.captureWarnings(True)

CHASSIS_PATH = "/redfish/v1/Chassis/System.Embedded.1"


def run():
    node_query = {
        "fields": [
            "name",
            "id",
            "driver_info",
            "properties",
        ],
        "limit": "1",
    }

    with openstack.connect() as conn:
        # List baremetal servers
        nodes: List[Node]
        nodes = conn.baremetal.nodes(**node_query)

        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            future_to_result = {
                executor.submit(get_node_info, node): node
                for node in nodes
                if ("P3" in node.name)
            }
            for future in concurrent.futures.as_completed(future_to_result):
                try:
                    data = future.result()
                except Exception as exc:
                    print(exc)


def _get_dell_oem_processor(proc: Processor) -> Mapping:
    cpu_dict: Mapping = proc.json

    try:
        delloem_dict = cpu_dict.get("Oem", {}).get("Dell", {}).get("DellProcessor", {})
        # print(json.dumps(delloem_dict, indent=2))
        return delloem_dict
    except KeyError:
        return {}


def _OneE3(mb: int):
    try:
        base = int(mb)
        return int(base * 1e3)
    except Exception as ex:
        # print(ex)
        return None


def _OneE6(mb: int):
    try:
        base = int(mb)
        return int(base * 1e6)
    except Exception as ex:
        # print(ex)
        return None


def _OneE9(mb: int):
    try:
        base = int(mb)
        return int(base * 1e9)
    except Exception as ex:
        # print(ex)
        return None


def get_node_info(node):

    # print(node.name, node.id, node.properties)
    bmc_addr = node.driver_info.get("ipmi_address")
    bmc_username = node.driver_info.get("ipmi_username")
    bmc_password = node.driver_info.get("ipmi_password")

    base_url = f"https://{bmc_addr}/redfish/v1"

    node_dict = {
        "type": "node",
        "uid": node.id,
        "node_name": node.name,
        "node_type": None,
        "placement": {},
        "network_adapters": [],
        "storage_devices": [],
        "supported_job_types": {
            "besteffort": False,
            "deploy": True,
            "virtual": "ivt",
        },
    }

    try:
        conn = sushy.Sushy(
            base_url=base_url,
            username=bmc_username,
            password=bmc_password,
            verify=False,
        )
        system = conn.get_system()
        chassis = conn.get_chassis(CHASSIS_PATH)
    except ConnectionError:
        print(f"failed to connect to {node.name} at {bmc_addr}")
        raise
    except AccessError:
        print(f"failed to access {node.name} at {bmc_addr}")
        raise

    print(f"querying {node.name} at {bmc_addr}")

    processors: List[Processor] = system.processors.get_members()
    cpu = processors[0]

    chassis_json: Mapping = chassis.json
    location = chassis_json.get("Location")

    # print(json.dumps(chassis_json, indent=2))

    system_json: Mapping = system.json
    oem_json: Mapping = system_json.get("Oem")

    try:
        bios_release_date = (
            oem_json.get("Dell", {}).get("DellSystem", {}).get("BIOSReleaseDate")
        )
    except KeyError:
        bios_release_date = None

    node_dict["chassis"] = {
        "manufacturer": system.manufacturer,
        "name": chassis.model,
        "serial": system.sku,
    }

    node_dict["bios"] = {
        "release_date": bios_release_date,
        "vendor": system.manufacturer,
        "version": system.bios_version,
    }

    num_cpu = len(processors)
    num_threads = int(cpu.total_threads) * num_cpu

    instruction_set = re.sub("-bit$", "", str(cpu.instruction_set))
    instruction_set = re.sub("\s", "_", instruction_set)

    node_dict["architecture"] = {
        "platform_type": instruction_set,
        "smp_size": num_cpu,
        "smt_size": num_threads,
    }

    dell_cpu_dict = _get_dell_oem_processor(cpu)

    current_clock_speed_hz = _OneE6(dell_cpu_dict.get("CurrentClockSpeedMhz"))

    node_dict["processor"] = {
        "cache_l1": _OneE3(dell_cpu_dict.get("Cache1SizeKB")),
        # "cache_l1d": None,
        # "cache_l1i": None,
        "cache_l2": _OneE3(dell_cpu_dict.get("Cache2SizeKB")),
        "cache_l3": _OneE3(dell_cpu_dict.get("Cache3SizeKB")),
        "clock_speed": current_clock_speed_hz,
        "instruction_set": re.sub("_", "-", instruction_set),
        "model": cpu.model,
        # "other_description": cpu.model,
        "vendor": cpu.manufacturer,
        "version": None,
    }

    placement_keys = location.get("InfoFormat").split(";")
    placement_vals = location.get("Info").split(";")
    placement_dict = {}
    for key, value in zip(placement_keys, placement_vals):
        placement_dict[key] = value

    node_dict["placement"] = {
        "node": placement_dict.get("RackSlot"),
        "rack": placement_dict.get("RackName"),
    }

    node_dict["gpu"] = {}

    mem = system.memory_summary

    node_dict["main_memory"] = {
        "humanized_ram_size": mem.size_gib,
        "ram_size": _OneE9(mem.size_gib),
    }
    node_dict["monitoring"] = {}

    adapters = network_adapters(chassis)
    adapter: NetworkAdapter
    for adapter in adapters.get_members():
        # print(json.dumps(adapter.json, indent=2))

        port: NetworkPort
        for port in adapter.ports().get_members():
            # print(json.dumps(port.json, indent=2))

            link_caps = port.link_capabilities

            port_dict = {
                "device": port.identity,
                "interface": link_caps[0].get("LinkNetworkTechnology"),
                "mac": str.lower(port.mac_address[0]),
                "model": adapter.model,
                "rate": link_caps[0].get("LinkSpeedMbps"),
                "vendor": adapter.manufacturer,
            }
            node_dict["network_adapters"].append(port_dict)

    for controller in system.storage.get_members():
        drives = controller.drives

        drive: Drive
        for drive in drives:
            storage_dict = {}
            drive_dict: Mapping = drive.json

            size_in_gb = int(drive.capacity_bytes / (1e9))

            # print(json.dumps(item.json, indent=2))
            storage_dict = {
                "device": drive.identity,
                # "driver": "megaraid_sas",
                "humanized_size": f"{size_in_gb} GB",
                "interface": drive_dict.get("Protocol"),
                "model": drive.model,
                "rev": drive_dict.get("Revision"),
                "size": drive.capacity_bytes,
                "vendor": drive.manufacturer,
            }
            node_dict["storage_devices"].append(storage_dict)

    # print(json.dumps(system.json, indent=2, sort_keys=True))
    # print(json.dumps(node_dict, indent=2, sort_keys=True))

    reference_filename = f"{node.id}.json"
    referencerepo_path = Path(
        "reference-repository/data/chameleoncloud/sites/uc/clusters/chameleon/nodes"
    )

    output_file = Path(referencerepo_path, reference_filename)
    with open(output_file, "w+") as f:
        json.dump(node_dict, f, indent=2, sort_keys=True)
        print(f"generated {output_file}")


def network_adapters(chassis: Chassis):
    """Property to reference `NetworkAdapterCollection` instance

    It is set once when the first time it is queried. On refresh,
    this property is marked as stale (greedy-refresh not done).
    Here the actual refresh of the sub-resource happens, if stale.
    """
    return NetworkAdapterCollection(
        chassis._conn,
        utils.get_sub_resource_path_by(chassis, "NetworkAdapters"),
        redfish_version=chassis.redfish_version,
        registries=chassis.registries,
        root=chassis.root,
    )


class NetworkPort(base.ResourceBase):
    identity = base.Field("Id", required=True)
    """The Ethernet adapter identity string"""

    name = base.Field("Name")
    """The name of the resource or array element"""

    mac_address = base.Field("AssociatedNetworkAddresses")

    link_capabilities = base.Field("SupportedLinkCapabilities")
    current_link_type = base.Field("ActiveLinkTechnology")
    current_link_speed_mbps = base.Field("CurrentLinkSpeedMbps")


class NetworkPortCollection(base.ResourceCollectionBase):
    @property
    def _resource_type(self):
        return NetworkPort


class NetworkAdapter(base.ResourceBase):
    """This class adds the NetworkAdapter resource"""

    identity = base.Field("Id", required=True)
    """The Ethernet adapter identity string"""

    name = base.Field("Name")
    """The name of the resource or array element"""

    model = base.Field("Model")
    """Model"""

    manufacturer = base.Field("Manufacturer")
    """Manufacturer"""

    def ports(self) -> NetworkPortCollection:
        return NetworkPortCollection(
            self._conn,
            utils.get_sub_resource_path_by(self, "NetworkPorts"),
            redfish_version=self.redfish_version,
            registries=self.registries,
            root=self.root,
        )

    status = common.StatusField("Status")
    """Describes the status and health of this adapter."""


class NetworkAdapterCollection(base.ResourceCollectionBase):
    @property
    def _resource_type(self):
        return NetworkAdapter

    @property
    @utils.cache_it
    def summary(self):
        """Summary of MAC addresses and adapters state

        This filters the MACs whose health is OK,
        which means the MACs in both 'Enabled' and 'Disabled' States
        are returned.

        :returns: dictionary in the format
            {'aa:bb:cc:dd:ee:ff': sushy.STATE_ENABLED,
            'aa:bb:aa:aa:aa:aa': sushy.STATE_DISABLED}
        """
        mac_dict = {}
        for eth in self.get_members():
            if eth.mac_address is not None and eth.status is not None:
                if eth.status.health == constants.HEALTH_OK:
                    mac_dict[eth.mac_address] = eth.status.state
        return mac_dict
