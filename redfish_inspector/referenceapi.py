#!python3

import json
import logging
from typing import List, Mapping

from openstack.baremetal.v1.node import Node
from sushy import exceptions as s_exec
from sushy import utils
from sushy.resources.chassis.chassis import Chassis
from sushy.resources.system import processor
from sushy.resources.system.processor import Processor
from sushy.resources.system.storage.drive import Drive
from sushy.resources.system.system import System

from redfish_inspector import constants as reference_constants
from redfish_inspector.redfish import NetworkAdapter, NetworkPort, PcieDevice


class ALVEO_U280(object):
    board_model = "Alveo U280"
    board_vendor = "Xilinx Corporation"
    fpga_model = "XCU280"
    fpga_vendor = "Xilinx Corporation"


FPGA_MAPPING = {
    "Xilinx Corporation": {
        "0x500c": ALVEO_U280(),
        "0x500d": ALVEO_U280(),
    }
}



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

    def __init__(self, node: Node):
        self.uid = node.id
        self.node_name = node.name
        self.type = ChameleonBaremetal.type
        self.supported_job_types = ChameleonBaremetal.supported_job_types
        self.network_adapters = []
        self.pcie_devices = []
        self.storage_devices = []
        self.gpu = {}

    def from_dict(self, node_dict: Mapping):
        for key, value in node_dict.items():
            setattr(self, key, value)

    def set_arch(self, system: System):
        cpu_summary = system.processors.summary

        processors = [
            proc
            for proc in system.processors.get_members()
            if proc.json.get("ProcessorType") == "CPU"
        ]
        sockets = len(processors)

        arch = cpu_summary.architecture
        if "x86-64" in arch:
            platform_type = "x86_64"
        else:
            platform_type = arch

        self.architecture = {
            "platform_type": platform_type,
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

        self.processor = {}
        proc_dict = proc.json

        delloem: Mapping = (
            proc_dict.get("Oem", {}).get("Dell", {}).get("DellProcessor", {})
        )
        redfish_values = {
            "model": proc.model,
            "vendor": proc.manufacturer,
            "version": proc_dict.get("Version"),
            "clock_speed": int(delloem.get("CurrentClockSpeedMhz", 0) * 1e6),
            "cache_l1": int(delloem.get("Cache1SizeKB", 0) * 1e3),
            "cache_l2": int(delloem.get("Cache2SizeKB", 0) * 1e3),
            "cache_l3": int(delloem.get("Cache3SizeKB", 0) * 1e3),
            "instruction_set": proc_dict.get("InstructionSet"),
        }

        for k, v in redfish_values.items():
            if v:

                self.processor.update({k: v})

    def set_chassis(self, chassis: Chassis):
        self.chassis = {
            "manufacturer": chassis.manufacturer,
            "name": chassis.model,
            "serial": chassis.sku,
        }

    def set_location(self, chassis: Chassis):
        """Get physical location from BMC info."""

        location: Mapping = chassis.json.get("Location")

        placement_keys = location.get("InfoFormat", "").split(";")
        placement_vals = location.get("Info", "").split(";")
        placement_dict = {}
        for key, value in zip(placement_keys, placement_vals):
            placement_dict[key] = value

        self.placement = {
            "node": placement_dict.get("RackSlot"),
            "rack": placement_dict.get("RackName"),
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
            "vendor": adapter.manufacturer,
            "enabled": enabled,
            "management": False,
        }

        link_speed_bps = link_caps[0].get("LinkSpeedMbps", 0)
        if link_speed_bps:
            port_dict.setdefault("rate", int(link_speed_bps * 1e6))

        self.network_adapters.append(port_dict)

    def add_storage(self, drive: Drive):
        size_in_gb = int(drive.capacity_bytes / (1e9))

        storage_dict = {
            "device": drive.identity,
            # "driver": "megaraid_sas",
            "humanized_size": f"{size_in_gb} GB",
            "interface": drive.json.get("Protocol"),
            "model": drive.model,
            "rev": drive.json.get("Revision"),
            "size": drive.capacity_bytes,
            "vendor": drive.manufacturer,
            "media_type": drive.media_type,
            # "serial_number": drive.serial_number,
            # "part_number": drive.part_number,
        }
        self.storage_devices.append(storage_dict)

    def add_pcie_dev(self, dev: PcieDevice):

        # don't add dummy devices
        # if dev.firmware_version or dev.part_number or dev.serial_number:
        # the first "function" is usually the main devices
        dev_name = dev.name

        # functions = []
        # for func in dev.functions():
        #     functions.append(
        #         {
        #             "name": func.name,
        #             "device_class": func.device_class,
        #             "class_code": func.class_code,
        #             "description": func.description,
        #             "SubsystemId": func.subsystem_id,
        #             "SubsystemVendorId": func.subsystem_vendor_id,
        #             "DeviceID": func.device_id,
        #             "VendorID": func.vendor_id,
        #         }
        #     )

        func = next(dev.functions())

        dev_dict = {
            "id": dev.identity,
            "name": dev_name,
            "manufacturer": dev.manufacturer,
            "firmware_version": dev.firmware_version,
            "part_number": dev.part_number,
            "serial_number": dev.serial_number,
            "device_class": func.device_class,
            "VendorID": func.vendor_id,
            "DeviceID": func.device_id,
        }
        # if func.device_class in (
        #     "ProcessingAccelerators",
        #     "NetworkController",
        # ):
        self.pcie_devices.append(dev_dict)

    def get_gpus(self):

        for d in self.pcie_devices:
            if d.get("device_class") == reference_constants.GPUDevice.device_class:
                matched_gpus = [g for g in reference_constants.GPU_CLASS_LIST if (g.VendorID == d.get("VendorID")) and (g.DeviceID == d.get("DeviceID"))]
                num_matches = len(matched_gpus)
                if num_matches == 1:
                    matched_gpu = matched_gpus[0]
                    if matched_gpu.ignore:
                        continue
                    else:
                        self.gpu["gpu"] = True
                        self.gpu["gpu_model"] = matched_gpu.name
                        self.gpu["gpu_name"] =  matched_gpu.friendly_name
                        self.gpu["gpu_vendor"] = matched_gpu.manufacturer
                        self.gpu["gpu_count"] = self.gpu.get("gpu_count", 0) + 1
                elif num_matches > 1:
                    logging.warn(f"Multiple matches found, {d} matched {matched_gpus}")
                elif num_matches == 0:
                    logging.warn(f"GPU found but not matched for device {d}")


    def get_fgpas(self):
        for device in self.pcie_devices:
            manufacturer = device.get("manufacturer")
            fpga_dict = FPGA_MAPPING.get(manufacturer, {})

            device_id = device.get("DeviceID")
            fpga_class = fpga_dict.get(device_id)

            if fpga_class:
                self.fpga = {
                    "board_vendor": fpga_class.board_vendor,
                    "board_model": fpga_class.board_model,
                    "fpga_vendor": fpga_class.fpga_vendor,
                    "fpga_model": fpga_class.fpga_model,
                }

    def check_infiniband(self):
        for dev in self.network_adapters:
            if dev.get("interface") == "InfiniBand":
                self.infiniband = True

    def check_node_type(self):

        node_class = None
        cpu_series = None
        variant = None

        chassis_model: str = self.chassis.get("name")

        if self.gpu.get("gpu"):
            node_class = "gpu"
            variant = self.gpu.get("gpu_model", "").replace(" ", "_").lower()

        elif "R740" in chassis_model:
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
            self.node_type = f"{node_class}_{cpu_series}"
        elif node_class == "gpu":
            self.node_type = f"{node_class}_{variant}"
        else:
            self.node_type = node_class
