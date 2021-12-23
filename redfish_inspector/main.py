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
    NetworkPort,
    network_adapters,
    pcie_devices,
)

# Initialize and turn on debug logging
openstack.enable_logging(debug=False)
logging.captureWarnings(True)

CHASSIS_PATH = "/redfish/v1/Chassis/System.Embedded.1"

NODE_NAMES = (
    # "nc45",
    "P3-CPU-038",
    "P3-SSD-010",
    # "P3-CPU-039",
    # "P3-CPU-040",
    # "P3-CPU-041",
    # "P3-CPU-042",
)


def run():
    node_query = {
        "fields": [
            "name",
            "id",
            "driver_info",
            "properties",
        ],
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
                if node.name in NODE_NAMES
            }
            for future in concurrent.futures.as_completed(future_to_result):
                try:
                    data = future.result()
                except AccessError or ConnectionError as exc:
                    print(exc)


def get_node_info(node: Node):

    # print(node.name, node.id, node.properties)
    bmc_addr = node.driver_info.get("ipmi_address")
    bmc_username = node.driver_info.get("ipmi_username")
    bmc_password = node.driver_info.get("ipmi_password")

    base_url = f"https://{bmc_addr}/redfish/v1"

    reference_node = referenceapi.ChameleonBaremetal(node=node)

    try:
        conn = sushy.Sushy(
            base_url=base_url,
            username=bmc_username,
            password=bmc_password,
            verify=False,
        )
    except ConnectionError:
        print(f"failed to connect to {node.name} at {bmc_addr}")
        raise
    except AccessError:
        print(f"failed to access {node.name} at {bmc_addr}")
        raise

    print(f"querying {node.name} at {bmc_addr}")
    system = conn.get_system()
    reference_node.set_arch(system)
    reference_node.set_bios(system)
    reference_node.set_memory(system)
    reference_node.set_monitoring()

    processors: List[Processor] = system.processors.get_members()
    cpu = processors[0]
    reference_node.set_processor(cpu)

    chassis = conn.get_chassis(CHASSIS_PATH)
    reference_node.set_chassis(chassis)

    ironic_mac = []
    port_query = {"node_id": node.id, "fields": ["address"]}
    # reuse connection
    os_connection = node._connection
    for os_port in os_connection.baremetal.ports(**port_query):
        ironic_mac.append(os_port.address)

    adapters = network_adapters(chassis)
    for adapter in adapters.get_members():
        port: NetworkPort
        for port in adapter.ports().get_members():
            enabled = False
            for mac in port.mac_address:
                if str.lower(mac) in ironic_mac:
                    enabled = True
                    break
            # print(port.mac_address, ironic_mac)
            reference_node.add_network_port(adapter, port, enabled)

    for pcie_dev in pcie_devices(system=system):
        reference_node.add_pcie_dev(pcie_dev)

    reference_node.get_gpus()

    reference_node.set_location(chassis)

    for controller in system.storage.get_members():
        drive: Drive
        for drive in controller.drives:
            reference_node.add_storage(drive)

    reference_node.check_infiniband()

    # reference_node.check_node_type()
    reference_filename = f"{node.id}.json"
    referencerepo_path = Path(
        "../reference-repository/data/chameleoncloud/sites/uc/clusters/chameleon/nodes"
    )

    output_dict: Mapping = reference_node.json()
    # remove entries not in current referenceapi
    output_dict.pop("pcie_devices")
    if not output_dict.get("gpu"):
        output_dict.pop("gpu")

    output_file = Path(referencerepo_path, reference_filename)
    with open(output_file, "w+") as f:
        json.dump(output_dict, f, indent=2, sort_keys=True)
        print(f"generated {output_file}")
