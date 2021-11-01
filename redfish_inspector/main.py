#!python3

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import List, Mapping

import openstack
import sushy
from openstack.baremetal.v1.node import Node
from openstack.baremetal.v1.port import Port
from openstack.cloud import exc
from sushy.main import Sushy
from sushy.resources.chassis.chassis import Chassis
from sushy.resources.system.processor import Processor
from sushy.resources.system.system import System
from urllib3.exceptions import InsecureRequestWarning

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

        node: Node or None
        node = next(nodes)

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
            "interfaces": [],
            "storage_devices": [],
        }
        conn = sushy.Sushy(
            base_url=base_url,
            username=bmc_username,
            password=bmc_password,
            verify=False,
        )

        system = conn.get_system()
        chassis = conn.get_chassis(CHASSIS_PATH)
        processors: List[Processor] = system.processors.get_members()
        cpu = processors[0]

        chassis_json: Mapping = chassis.json

        location = chassis_json.get("Location")

        node_dict["chassis"] = {
            "manufacturer": system.manufacturer,
            "name": chassis.model,
            "serial": system.sku,
        }

        node_dict["bios"] = {
            "release_date": None,
            "vendor": None,
            "version": system.bios_version,
        }

        node_dict["architecture"] = {
            "platform_type": cpu.instruction_set,
            "smp_size": len(processors),
            "smt_size": cpu.total_threads,
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

        # print(json.dumps(placement_dict, indent=2))
        print(json.dumps(node_dict, indent=2, sort_keys=True))
