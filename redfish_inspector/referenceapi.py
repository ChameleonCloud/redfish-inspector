#!python3

import json
from typing import Mapping, List


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

    gpu = {
        "gpu": False,
    }

    GPU_TYPES = (
        "TU102GL [Quadro RTX 6000/8000]",
        "GV100GL [Tesla V100 SXM2 32GB]",
    )

    pcie_devices = []
    network_adapters = []

    def __init__(self, node_info: Mapping):
        for key, value in node_info.items():
            setattr(self, key, value)

    def get_gpus(self):

        gpu_dict = self.gpu.copy()

        for device in self.pcie_devices:
            if device.get("name") in self.GPU_TYPES:
                gpu_dict["gpu"] = True
                gpu_dict["gpu_model"] = device.get("name")
                gpu_dict["gpu_vendor"] = device.get("manufacturer")
                gpu_dict["gpu_count"] = gpu_dict.get("gpu_count", 0) + 1
        return gpu_dict

    def check_infiniband(self):
        ifaces: List[Mapping] = self.network_adapters.copy()
        for dev in ifaces:
            if dev.get("interface") == "InfiniBand":
                return True
            else:
                return False

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
