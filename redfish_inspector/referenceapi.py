#!python3

import json
from typing import Mapping


class G5kNode:
    uid = None
    node_type = None
    node_name = None

    def json(self):
        return self.__dict__


class ChameleonBaremetal(G5kNode):
    type = "node"
    supported_job_types = {
        "besteffort": False,
        "deploy": True,
        "virtual": "ivt",
    }

    chassis = {
        "manufacturer": None,
        "name": None,
        "serial": None,
    }

    processor = {
        "model": None,
        "other_description": None,
        "vendor": None,
        "version": None,
    }

    def __init__(self, node_info: Mapping):
        for key, value in node_info.items():
            setattr(self, key, value)

    def check_node_type(self):

        node_class = None
        cpu_series = None
        variant = None

        chassis_model: str = self.chassis.get("name")

        if "R740" in chassis_model:
            node_class = "compute"
        elif "R6515" in chassis_model:
            node_class = "mgmt"
        elif "R6525" in chassis_model:
            node_class = "storage_nvme"
        elif "C4140" in chassis_model:
            node_class = "gpu_v100"
        elif "R840" in chassis_model:
            node_class = "compute_nvdimm"

        cpu_model: str = self.processor.get("model")
        if "Gold 6126" in cpu_model:
            cpu_series = "skylake"
        if "Gold 6240R" in cpu_model:
            cpu_series = "cascadelake_r"

        if node_class == "compute":
            return f"{node_class}_{cpu_series}"
        else:
            return node_class
