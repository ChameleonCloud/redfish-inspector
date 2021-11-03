#!python3


import concurrent.futures
import json
import logging
import re
from pathlib import Path
from typing import List, Mapping

import openstack
import sushy
from openstack import connection
from openstack.baremetal.v1.node import Node
from openstack.baremetal.v1.port import Port
from sushy.exceptions import AccessError, ConnectionError
from sushy.resources.system.processor import Processor
from sushy.resources.system.storage.drive import Drive

from redfish_inspector import referenceapi
from redfish_inspector.redfish import (
    NetworkAdapter,
    NetworkAdapterCollection,
    NetworkPort,
    NetworkPortCollection,
    network_adapters,
    PcieDevice,
    pcie_devices,
)


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

    conn: connection.Connection
    with openstack.connect() as conn:
        # List baremetal servers
        nodes: List[Node]
        nodes = conn.baremetal.nodes(**node_query)

        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            future_to_result = {
                executor.submit(get_node_info, node): node
                for node in nodes
                # if ("nc16" in node.name) or ("GPU" in node.name)
                if ("P3" in node.name)
            }
            for future in concurrent.futures.as_completed(future_to_result):
                try:
                    data = future.result()
                except AccessError or ConnectionError as exc:
                    print(exc)


def _get_dell_oem_processor(proc: Processor) -> Mapping:
    cpu_dict: Mapping = proc.json

    try:
        delloem_dict = cpu_dict.get("Oem", {}).get("Dell", {}).get("DellProcessor", {})

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
        "pcie_devices": [],
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

    pcie_devs = pcie_devices(system=system)
    for dev in pcie_devs:

        # print(json.dumps(dev.json, indent=2))
        # print(dev.pcie_functions)

        if (
            (dev.firmware_version)
            or (dev.part_number)
            or (dev.serial_number)
            or ("NVIDIA" in dev.manufacturer)
        ):

            dev_name = dev.name
            for func in dev.functions():
                if func.function_id == 0:
                    dev_name = func.name

            dev_dict = {
                "id": dev.identity,
                "name": dev_name,
                "manufacturer": dev.manufacturer,
                "firmware_version": dev.firmware_version,
                "part_number": dev.part_number,
                "serial_number": dev.serial_number,
            }

            node_dict["pcie_devices"].append(dev_dict)

    placement_keys = location.get("InfoFormat").split(";")
    placement_vals = location.get("Info").split(";")
    placement_dict = {}
    for key, value in zip(placement_keys, placement_vals):
        placement_dict[key] = value

    node_dict["placement"] = {
        "node": placement_dict.get("RackSlot"),
        "rack": placement_dict.get("RackName"),
    }

    mem = system.memory_summary

    node_dict["main_memory"] = {
        "humanized_ram_size": f"{mem.size_gib} GiB",
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
                "rate": _OneE6(link_caps[0].get("LinkSpeedMbps")),
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

            storage_dict = {
                "device": drive.identity,
                # "driver": "megaraid_sas",
                "humanized_size": f"{size_in_gb} GB",
                "interface": drive_dict.get("Protocol"),
                "model": drive.model,
                "rev": drive_dict.get("Revision"),
                "size": drive.capacity_bytes,
                "vendor": drive.manufacturer,
                "media_type": drive.media_type,
            }
            node_dict["storage_devices"].append(storage_dict)

    # print(json.dumps(system.json, indent=2, sort_keys=True))
    # print(json.dumps(node_dict, indent=2, sort_keys=True))

    node_obj = referenceapi.ChameleonBaremetal(node_dict)

    node_dict["node_type"] = node_obj.check_node_type()

    gpu_dict = node_obj.get_gpus()
    if gpu_dict.get("gpu"):
        node_dict["gpu"] = gpu_dict

    if node_obj.check_infiniband():
        node_dict["infiniband"] = True

    # node_dict.pop("pcie_devices")

    reference_filename = f"{node.id}.json"
    referencerepo_path = Path(
        "reference-repository/data/chameleoncloud/sites/uc/clusters/chameleon/nodes"
    )

    output_file = Path(referencerepo_path, reference_filename)
    with open(output_file, "w+") as f:
        json.dump(node_dict, f, indent=2, sort_keys=True)
        print(f"generated {output_file}")
