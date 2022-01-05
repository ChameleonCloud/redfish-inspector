#!python3


from sushy import utils
from sushy.resources import base, chassis, common, constants
from sushy.resources.chassis.chassis import Chassis
from sushy.resources.system.system import System


def pcie_devices(system: System):
    """Property to reference `PCIeDevices` instance

    It is set once when the first time it is queried. On refresh,
    this property is marked as stale (greedy-refresh not done).
    Here the actual refresh of the sub-resource happens, if stale.
    """

    # "@odata.id": "/redfish/v1/Systems/System.Embedded.1/PCIeDevices/59-0"
    for path in utils.get_sub_resource_path_by(
        system, "PCIeDevices", is_collection=True
    ):
        yield PcieDevice(
            system._conn,
            path,
            redfish_version=system.redfish_version,
            registries=system.registries,
            root=system.root,
        )


class PcieDevice(base.ResourceBase):
    identity = base.Field("Id", required=True)
    """The PcieDevice adapter identity string"""

    name = base.Field("Name")
    """The name of the resource or array element"""

    model = base.Field("Model")
    """The name of the resource or array element"""

    manufacturer = base.Field("Manufacturer")
    """The name of the resource or array element"""

    firmware_version = base.Field("FirmwareVersion")
    """The name of the resource or array element"""

    part_number = base.Field("PartNumber")
    """The name of the resource or array element"""

    serial_number = base.Field("SerialNumber")
    """The name of the resource or array element"""

    def functions(self):
        paths = utils.get_sub_resource_path_by(
            self,
            ["Links", "PCIeFunctions"],
            is_collection=True,
        )
        for path in paths:
            yield PcieFunction(
                self._conn,
                path,
                redfish_version=self.redfish_version,
                registries=self.registries,
                root=self.root,
            )


class PcieFunction(base.ResourceBase):
    identity = base.Field("Id", required=True)
    """The PcieFunction adapter identity string"""

    name = base.Field("Name")
    """The name of the resource or array element"""

    description = base.Field("Description")
    device_class = base.Field("DeviceClass")
    class_code = base.Field("ClassCode")
    function_id = base.Field("FunctionId")
    subsystem_id = base.Field("SubsystemId")
    subsystem_vendor_id = base.Field("SubsystemVendorId")
    device_id = base.Field("DeviceId")
    vendor_id = base.Field("VendorId")


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
