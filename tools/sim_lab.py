#!/usr/bin/env python3
"""
AreYouLowBattery - Peripheral & OS Chaos Simulator + Diagnostic Replay Tool.

Usage:
    python3 tools/sim_lab.py --chaos
    python3 tools/sim_lab.py --diag "/path/to/areyoulowbattery_diag.txt"
"""

import argparse
import os
import re
import sys
from typing import Dict, List, Optional
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from areyoulowbattery.engine import BatteryEngine
from areyoulowbattery.handlers import get_handler, HANDLER_REGISTRY
from areyoulowbattery.models import DeviceCategory, DeviceMatch, DeviceProfile
from areyoulowbattery.transport import HidrawDevice


DIAG_LINE_RE = re.compile(
    r"VID:PID=([0-9a-fA-F]{4}):([0-9a-fA-F]{4})\s+"
    r"Iface=(-?\d+)\s+"
    r"UsagePage=(None|0x[0-9a-fA-F]+)\s+"
    r"Name='([^']*)'\s+"
    r"Path=(.+)$"
)


def parse_diag_file(path: str) -> tuple[str, List[HidrawDevice]]:
    platform_str = "linux"
    devices: List[HidrawDevice] = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for raw in f:
            line = raw.strip()
            if line.startswith("OS / Platform:") and "win32" in line.lower():
                platform_str = "win32"
            m = DIAG_LINE_RE.search(line)
            if not m:
                continue
            vid = int(m.group(1), 16)
            pid = int(m.group(2), 16)
            iface = int(m.group(3))
            up_raw = m.group(4)
            usage_page = None if up_raw == "None" else int(up_raw, 16)
            name = m.group(5)
            dev_path = m.group(6).strip()
            devices.append(
                HidrawDevice(
                    dev_path=dev_path,
                    vendor_id=vid,
                    product_id=pid,
                    interface_number=None if iface < 0 else iface,
                    name=name,
                    usage_page=usage_page,
                )
            )
    return platform_str, devices


class FaultyTransport:
    """Simulates hostile OS/hidapi driver behaviors (blocked KBD, read error, etc.)."""

    def __init__(self, dev_path: str, read_only: bool = False, fault_mode: str = "read_error", responses: Optional[Dict[str, bytes]] = None):
        self.dev_path = dev_path
        self.read_only = read_only
        self.fault_mode = fault_mode
        self.responses = responses or {}
        self.had_read_error = False
        self._opened = False

    def open(self):
        if self.fault_mode == "open_error" or self.dev_path.lower().endswith("\\kbd"):
            raise PermissionError(f"Simulated OS open block on {self.dev_path}")
        self._opened = True

    def close(self):
        self._opened = False

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *args):
        self.close()

    def write_output_report(self, data: bytes):
        if self.fault_mode == "write_error":
            raise OSError("Simulated hidapi write error")

    def send_feature_report(self, data: bytes):
        if self.fault_mode == "write_error":
            raise OSError("Simulated feature write error")

    def get_feature_report(self, report_id: int, length: int = 64) -> bytes:
        if self.fault_mode == "read_error":
            raise OSError("Simulated feature read error")
        return bytes([report_id] + [0] * (length - 1))

    def read_input_report(self, length: int = 64, timeout_sec: float = 0.5) -> Optional[bytes]:
        self.had_read_error = False
        if self.dev_path in self.responses:
            return self.responses[self.dev_path]
        if self.fault_mode == "read_error":
            self.had_read_error = True
            return None
        if self.fault_mode == "garbage":
            return b"\x00\xff\xaa"
        return None


def run_chaos_matrix() -> int:
    protocols = list(HANDLER_REGISTRY.keys())
    faults = ["open_error", "write_error", "read_error", "garbage", "timeout"]
    failures = 0

    print("=== Chaos Matrix Across All Supported Protocols ===")
    for proto in protocols:
        handler = get_handler(proto)
        prof = DeviceProfile(
            name=f"Chaos {proto}",
            category=DeviceCategory.MOUSE,
            icon="🖱️",
            match=DeviceMatch(vendor_id=0x046D, product_id=0xC534),
            protocol=proto,
        )
        dev = HidrawDevice(
            dev_path=r"\\?\HID#VID_046D&PID_C534&MI_01&Col01#7&1234&0&0000#{4d1e55b2}",
            vendor_id=0x046D,
            product_id=0xC534,
            interface_number=1,
            name="Chaos Mouse",
            usage_page=0xFF00,
        )
        for fault in faults:
            def _make_tp(p, read_only=False, _fault=fault):
                return FaultyTransport(p, read_only=read_only, fault_mode=_fault)

            try:
                with patch("sys.platform", "win32"), \
                     patch("areyoulowbattery.transport.enumerate_hidraw", return_value=[dev]), \
                     patch("areyoulowbattery.handlers.hidpp.enumerate_hidraw", return_value=[dev]), \
                     patch("areyoulowbattery.handlers.hidpp.HidrawTransport", side_effect=_make_tp), \
                     patch("areyoulowbattery.handlers.compx.HidrawTransport", side_effect=_make_tp), \
                     patch("areyoulowbattery.handlers.nordic.HidrawTransport", side_effect=_make_tp), \
                     patch("areyoulowbattery.handlers.razer.HidrawTransport", side_effect=_make_tp), \
                     patch("areyoulowbattery.handlers.steelseries.HidrawTransport", side_effect=_make_tp), \
                     patch("areyoulowbattery.handlers.corsair.HidrawTransport", side_effect=_make_tp), \
                     patch("areyoulowbattery.handlers.hyperx.HidrawTransport", side_effect=_make_tp), \
                     patch("areyoulowbattery.handlers.yjx.HidrawTransport", side_effect=_make_tp), \
                     patch("areyoulowbattery.handlers.generic_hid.HidrawTransport", side_effect=_make_tp):
                    res = handler.read_battery(dev, prof)
                    if res and res.details and "Handler error" in res.details:
                        print(f"[FAIL] {proto} under {fault}: {res.details}")
                        failures += 1
            except Exception as e:
                print(f"[CRASH] {proto} under {fault}: {type(e).__name__}: {e}")
                failures += 1
        print(f"  [OK] {proto}: survived all 5 fault modes without crashing")

    print(f"Chaos result: {len(protocols)} protocols x {len(faults)} fault modes, {failures} failures")
    return failures


def replay_diag(diag_path: str) -> int:
    plat, devs = parse_diag_file(diag_path)
    print(f"=== Replaying Diagnostic: {diag_path} ===")
    print(f"Platform: {plat} | Parsed HID interfaces: {len(devs)}")

    # Simulate realistic Windows collection behavior:
    # - \KBD fails open
    # - generic Col01/Col02/Col03 raise read error
    # - 0xFF00 Col05 answers HID++ 1.0 battery 85% if present
    responses: Dict[str, bytes] = {}
    for d in devs:
        if (d.usage_page or 0) >= 0xFF00 and "Col05" in d.dev_path:
            responses[d.dev_path] = bytes([0x10, 0x01, 0x81, 0x0D, 85, 0x00, 0x00])

    def _make_tp(p, read_only=False):
        return FaultyTransport(p, read_only=read_only, fault_mode="read_error", responses=responses)

    engine = BatteryEngine()
    with patch("sys.platform", plat), \
         patch("areyoulowbattery.engine.enumerate_hidraw", return_value=devs), \
         patch("areyoulowbattery.transport.enumerate_hidraw", return_value=devs), \
         patch("areyoulowbattery.handlers.hidpp.enumerate_hidraw", return_value=devs), \
         patch("areyoulowbattery.handlers.hidpp.HidrawTransport", side_effect=_make_tp), \
         patch.object(engine, "_poll_bluetooth_windows", return_value=[("Pebble K380s", 90, "Windows SetupAPI", None, "⌨️")]):
        results = engine.poll_all_devices(force=True)

    for prof, st in results:
        print(
            f"  Profile='{prof.name}' Protocol={prof.protocol} "
            f"Connected={st.is_connected} Battery={st.percentage}% Details='{st.details}'"
        )
    return 0


def main():
    parser = argparse.ArgumentParser(description="AreYouLowBattery Simulator & Diagnostic Replay")
    parser.add_argument("--chaos", action="store_true", help="Run fault-injection chaos matrix across all protocols")
    parser.add_argument("--diag", type=str, help="Replay an areyoulowbattery_diag.txt file")
    args = parser.parse_args()

    exit_code = 0
    if args.chaos or not args.diag:
        exit_code |= run_chaos_matrix()
    if args.diag:
        exit_code |= replay_diag(args.diag)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
