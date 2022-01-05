"""Common values for CPUID lookup."""


class ReferenceProc(object):
    cache_l1 = None
    cache_l1d = None
    cache_l1i = None
    cache_l2 = None
    cache_l3 = None
    clock_speed = None
    instruction_set = None
    model = None
    other_description = None
    vendor = None
    version = None

    def get_reference_json(self):
        return {
            "cache_l1": self.cache_l1,
            "cache_l1d": self.cache_l1d,
            "cache_l1i": self.cache_l1i,
            "cache_l2": self.cache_l2,
            "cache_l3": self.cache_l3,
            "clock_speed": self.clock_speed,
            "instruction_set": self.instruction_set,
            "model": self.model,
            "other_description": self.other_description,
            "vendor": self.vendor,
            "version": self.version,
        }


class RedfishProc(object):
    model = None
    ProcessorArchitecture = None
    ProcessorId = {
        "EffectiveFamily": None,
        "EffectiveModel": None,
        "IdentificationRegisters": None,
        "MicrocodeInfo": None,
        "Step": None,
        "VendorId": None,
    }


class GenuineIntel(ReferenceProc):
    def __init__(self) -> None:
        super().__init__()
        self.vendor = "Intel"


class IntelXeonGold6240R(GenuineIntel, RedfishProc):
    def __init__(self) -> None:
        super().__init__()
        self.model = "Intel Xeon"
        self.ProcessorArchitecture = "x86"
        self.instruction_set = "x86-64"
        self.ProcessorId = {
            "EffectiveFamily": "6",
            "EffectiveModel": "85",
            "IdentificationRegisters": "0x00050657",
            "MicrocodeInfo": "0x5003005",
            "Step": "7",
            "VendorId": "GenuineIntel",
        }


class IntelXeonGold6126(GenuineIntel, RedfishProc):
    def __init__(self) -> None:
        super().__init__()
        self.cache_l1 = None
        self.cache_l1d = 32768
        self.cache_l1i = 32768
        self.cache_l2 = 1048576
        self.cache_l3 = 20185088
        self.clock_speed = 2600000000
        self.instruction_set = "x86-64"
        self.model = "Intel Xeon"
        self.other_description = "Intel(R) Xeon(R) Gold 6126 CPU @ 2.60GHz"
        self.vendor = "Intel"
        self.ProcessorArchitecture = "x86"
        self.ProcessorId = {
            "EffectiveFamily": "6",
            "EffectiveModel": "85",
            "IdentificationRegisters": "0x00050654",
            "MicrocodeInfo": None,
            "Step": "4",
            "VendorId": "GenuineIntel",
        }


class IntelXeonGold6230(GenuineIntel, RedfishProc):
    def __init__(self) -> None:
        super().__init__()


class IntelXeonPlatinum8276(GenuineIntel, RedfishProc):
    def __init__(self) -> None:
        super().__init__()


class AuthenticAMD(ReferenceProc):
    def __init__(self) -> None:
        super().__init__()
        self.vendor = "AMD"


class AMD_7352(AuthenticAMD, RedfishProc):
    def __init__(self) -> None:
        super().__init__()
        self.model = "AMD EPYC"
        self.ProcessorArchitecture = "x86"
        self.instruction_set = "x86-64"
        self.ProcessorId = {
            "EffectiveFamily": "15",
            "EffectiveModel": "49",
            "IdentificationRegisters": "0x00830F10",
            "MicrocodeInfo": "0x830104D",
            "Step": "0",
            "VendorId": "AuthenticAMD",
        }


CPU_MODEL_MAPPING = {
    "AMD EPYC 7352 24-Core Processor": AMD_7352(),
    "Intel(R) Xeon(R) Gold 6240R CPU @ 2.40GHz": IntelXeonGold6240R(),
    "Intel(R) Xeon(R) Gold 6126 CPU @ 2.60GHz": IntelXeonGold6126(),
    "Intel(R) Xeon(R) Platinum 8276 CPU @ 2.20GHz": IntelXeonPlatinum8276(),
    "Intel(R) Xeon(R) Gold 6230 CPU @ 2.10GHz": IntelXeonGold6230(),
}
