#!python3

import argparse
import json
import logging
import sys
from typing import List
from pathlib import Path

import openstack
from openstack.baremetal.v1.node import Node
from openstack.baremetal.v1.port import Port

# Initialize and turn on debug logging
openstack.enable_logging(debug=False)


def run():

    node_query = {
        "fields": [
            "name",
            "id",
            "driver_info",
            "properties",
        ],
    }

    with openstack.connect() as conn:
        # List baremetal servers
        node: Node
        for node in conn.baremetal.nodes(**node_query):
            # print(node.name, node.id, node.properties)
            bmc_addr = node.driver_info.get("ipmi_address")

            reference_filename = f"{node.id}.json"
            referencerepo_path = Path(
                "reference-repository/data/chameleoncloud/sites/uc/clusters/chameleon/nodes"
            )

            output_file = Path(referencerepo_path, reference_filename)
            print(f"querying {bmc_addr} to generate {output_file}")

            ref_dict = {
                "type": "node",
                "uid": node.id,
                "node_name": node.name,
                "supported_job_types": {
                    "besteffort": False,
                    "deploy": True,
                    "virtual": "ivt",
                },
            }

            # with open(output_file, "w+") as f:
            # json.dump(ref_dict, f, indent=2, sort_keys=True)
