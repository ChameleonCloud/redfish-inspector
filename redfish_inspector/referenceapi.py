#!python3

import json
from typing import Mapping, List
from openstack.baremetal.v1.node import Node
from sushy.resources.chassis.chassis import Chassis
from sushy.resources.system.system import System
from sushy.resources.system import processor
from sushy.resources.system.processor import Processor
from redfish_inspector.redfish import NetworkPort, NetworkAdapter


class G5kNode:
    uid = None
    node_type = None
    node_name = None

    def json(self):
        return self.__dict__


# class NetworkInterface:
#     pass


# class chassis:
#     pass


# class processor:
#     pass


# class Gpu:
#     pass


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

    # gpu = {
    #     "gpu": False,
    # }

    # GPU_TYPES = (
    #     "TU102GL [Quadro RTX 6000/8000]",
    #     "GV100GL [Tesla V100 SXM2 32GB]",
    # )

    def __init__(self, node: Node):
        self.uid = node.id
        self.node_name = node.name
        self.type = ChameleonBaremetal.type
        self.supported_job_types = ChameleonBaremetal.supported_job_types
        self.network_adapters = []
        self.pcie_devices = []

    def from_dict(self, node_dict: Mapping):
        for key, value in node_dict.items():
            setattr(self, key, value)

    def set_arch(self, system: System):
        cpu_summary = system.processors.summary
        sockets = len(system.processors.get_members())

        self.architecture = {
            "platform_type": cpu_summary.architecture,
            "smp_size": sockets,
            "smt_size": cpu_summary.count,
        }

    def set_bios(self, system: System):
        delloem = system.json.get("Oem", {}).get("Dell", {}).get("DellSystem", {})
        self.bios = {
            "release_date": delloem.get("BIOSReleaseDate", None),
            "vendor": system.manufacturer,
            "version": system.bios_version,
        }

    def set_memory(self, system: System):
        mem = system.memory_summary
        self.main_memory = {
            "humanized_ram_size": f"{mem.size_gib} GiB",
            "ram_size": int(mem.size_gib * 1e9),
        }

    def set_monitoring(self):
        self.monitoring = {"wattmeter": False}

    def set_processor(self, proc: Processor):
        self.processor = {
            "instruction_set": proc.instruction_set,
            "model": proc.model,
            "other_description": proc.model,
            "vendor": proc.manufacturer,
            "version": {
                "family": proc.processor_id.effective_family,
                "model": proc.processor_id.effective_model,
                "cpuid": proc.processor_id.identification_registers,
                "microcode": proc.processor_id.microcode_info,
                "step": proc.processor_id.step,
            },
        }

        delloem: Mapping = (
            proc.json.get("Oem", {}).get("Dell", {}).get("DellProcessor", {})
        )
        if delloem:
            self.processor.update(
                {
                    "clock_speed": int(delloem.get("CurrentClockSpeedMhz", 0) * 1e6),
                    "cache_l1": int(delloem.get("Cache1SizeKB", 0) * 1e3),
                    "cache_l2": int(delloem.get("Cache2SizeKB", 0) * 1e3),
                    "cache_l3": int(delloem.get("Cache3SizeKB", 0) * 1e3),
                }
            )

        # print(json.dumps(delloem, indent=2))

    def set_chassis(self, chassis: Chassis):
        self.chassis = {
            "manufacturer": chassis.manufacturer,
            "name": chassis.model,
            "serial": chassis.sku,
        }

    def add_network_port(
        self, adapter: NetworkAdapter, port: NetworkPort, enabled: bool
    ):

        link_caps = port.link_capabilities
        port_dict = {
            "device": port.identity,
            "interface": link_caps[0].get("LinkNetworkTechnology"),
            "mac": str.lower(port.mac_address[0]),
            "model": adapter.model,
            "rate": int(link_caps[0].get("LinkSpeedMbps") * 1e6),
            "vendor": adapter.manufacturer,
            "enabled": enabled,
        }
        self.network_adapters.append(port_dict)

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
