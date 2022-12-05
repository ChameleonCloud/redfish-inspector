class PcieDevice(object):
    ignore = False
    VendorID=None
    DeviceID=None
    device_class = None
    name = None
    manufacturer = None
    firmware_version = None
    part_number = None
    serial_number = None

class GPUDevice(PcieDevice):
    device_class='DisplayController'

class NvidiaGPUDevice(GPUDevice):
    manufacturer = 'NVIDIA Corporation'
    VendorID='0x10de'

class A100_PCIE_40G(NvidiaGPUDevice):
    name = 'GA100 [A100 PCIe 40GB]'
    friendly_name = "A100"
    manufacturer = 'NVIDIA Corporation'
    VendorID='0x10de'
    DeviceID='0x20f1'

class A100_PCIE_80G(NvidiaGPUDevice):
    name = 'GA100 [A100 PCIe 80GB]'
    friendly_name = "A100"
    manufacturer = 'NVIDIA Corporation'

class A100_SXM4_80G(NvidiaGPUDevice):
    name = 'GA100 [A100 PCIe 80GB]'
    friendly_name = "A100"
    manufacturer = 'NVIDIA Corporation'

class V100_SXM2_32G(NvidiaGPUDevice):
    name = "GV100GL [Tesla V100 SXM2 32GB]"
    friendly_name = "V100"
    manufacturer = 'NVIDIA Corporation'

class V100_PCIe_32G(NvidiaGPUDevice):
    name = "GV100GL [Tesla V100 PCIe 32GB]"
    friendly_name = "V100"
    manufacturer = 'NVIDIA Corporation'

class P100_PCIe_16GB(NvidiaGPUDevice):
    name = 'GP100GL [Tesla P100 PCIe 16GB]'
    friendly_name = "P100"
    DeviceID = "0x15f8"


class RTX_6000(NvidiaGPUDevice):
    name = "TU102GL [Quadro RTX 6000/8000]"
    friendly_name = "RTX6000"
    manufacturer = 'NVIDIA Corporation'

class AMDGPUDevice(GPUDevice):
    manufacturer = "Advanced Micro Devices, Inc. [AMD/ATI]"
    VendorID="0x1002"

class MI100(AMDGPUDevice):
    name = 'Arcturus GL-XL [AMD Instinct MI100]'
    DeviceID = '0x738c'
    friendly_name = "MI100"

class MatroxG200eW3(GPUDevice):
    name = 'Integrated Matrox G200eW3 Graphics Controller'
    manufacturer = 'Matrox Electronics Systems Ltd.'
    VendorID = '0x102b'
    DeviceID = '0x0536'
    ignore = True # Integrated graphics

class MatroxG200eR2(GPUDevice):
    name = 'G200eR2'
    manufacturer = 'Matrox Electronics Systems Ltd.'
    VendorID = '0x102b'
    DeviceID = '0x0534'
    ignore = True # Integrated graphics


GPU_CLASS_LIST = [
    A100_PCIE_40G,
    A100_PCIE_80G,
    A100_SXM4_80G,
    V100_PCIe_32G,
    V100_SXM2_32G,
    RTX_6000,
    MI100,
    MatroxG200eW3,
    MatroxG200eR2
]
