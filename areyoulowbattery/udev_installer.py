"""
Automated udev rules installer for Linux systems (pkexec / Polkit).
Completely bypassed and invisible on Windows.
"""

import os
import sys
import shutil
import subprocess
import tempfile
from typing import Optional

from areyoulowbattery.profile_loader import get_resource_dir
from areyoulowbattery.clean_env import get_clean_env
from areyoulowbattery.logger import logger


TARGET_RULES_PATH = "/etc/udev/rules.d/99-areyoulowbattery.rules"
FALLBACK_SYSTEM_RULES_PATH = "/usr/lib/udev/rules.d/99-areyoulowbattery.rules"


def are_udev_rules_installed() -> bool:
    """Returns True if the hardened udev rules are installed and up to date on Linux."""
    if not sys.platform.startswith("linux"):
        return True

    installed_path = None
    if os.path.exists(TARGET_RULES_PATH):
        installed_path = TARGET_RULES_PATH
    elif os.path.exists(FALLBACK_SYSTEM_RULES_PATH):
        installed_path = FALLBACK_SYSTEM_RULES_PATH

    if not installed_path:
        return False

    try:
        with open(installed_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            # Verify security hardening: must include peripheral vendor IDs
            if "1d57" in content and "25a7" in content and "046d" in content:
                return True
    except Exception as e:
        logger.debug("Failed to read udev rules at %s: %s", installed_path, e)

    return False


def get_rules_source_path() -> Optional[str]:
    """Finds the bundled 99-areyoulowbattery.rules or creates a temporary copy."""
    src = os.path.join(get_resource_dir(), "rules", "99-areyoulowbattery.rules")
    if os.path.exists(src):
        return src

    # Alternative paths (repository root / local install)
    alt = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "rules", "99-areyoulowbattery.rules")
    if os.path.exists(alt):
        return alt

    return None


def install_udev_rules(parent=None) -> bool:
    """
    Installs the 99-areyoulowbattery.rules using pkexec graphical authorization.
    Never runs on Windows. Returns True on success, False if canceled or failed.
    """
    if not sys.platform.startswith("linux"):
        return False

    from PySide6.QtWidgets import QMessageBox

    rules_src = get_rules_source_path()
    if not rules_src or not os.path.exists(rules_src):
        if parent:
            QMessageBox.critical(
                parent,
                "Error",
                "Could not locate 99-areyoulowbattery.rules file.\n\nPlease reinstall AreYouLowBattery."
            )
        return False

    pkexec_path = shutil.which("pkexec")
    if not pkexec_path:
        if parent:
            QMessageBox.warning(
                parent,
                "pkexec Not Found",
                "polkit 'pkexec' utility was not found on your system.\n\n"
                f"Please manually install the rules in terminal:\n\n"
                f"sudo cp '{rules_src}' {TARGET_RULES_PATH}\n"
                f"sudo udevadm control --reload && sudo udevadm trigger"
            )
        return False

    # Prefer standalone helper script if present, otherwise direct install binary
    script_path = os.path.join(get_resource_dir(), "rules", "install_udev.sh")
    if not os.path.exists(script_path):
        script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "rules", "install_udev.sh")

    if os.path.exists(script_path):
        pkexec_cmd = ["pkexec", script_path, rules_src]
    else:
        # Fallback to direct install binary invocation without shell interpolation
        pkexec_cmd = ["pkexec", "/usr/bin/install", "-m", "0644", rules_src, TARGET_RULES_PATH]

    try:
        proc = subprocess.run(
            pkexec_cmd,
            env=get_clean_env(),
            capture_output=True,
            text=True,
            timeout=60,
        )

        if proc.returncode == 0:
            # If we used fallback, reload udev
            if pkexec_cmd[1] != script_path:
                try:
                    subprocess.run(["udevadm", "control", "--reload"], env=get_clean_env(), timeout=5)
                    subprocess.run(["udevadm", "trigger"], env=get_clean_env(), timeout=5)
                except Exception:
                    pass

            if parent:
                QMessageBox.information(
                    parent,
                    "Permissions Configured",
                    "✓ udev rules installed successfully!\n\n"
                    "Your 2.4G wireless peripherals are now accessible without root."
                )
            return True
        elif proc.returncode in (126, 127):
            # User dismissed the graphical authentication prompt
            logger.info("udev rule installation canceled by user (exit code %d)", proc.returncode)
            return False
        else:
            err = proc.stderr.strip() or proc.stdout.strip() or f"Process exited with code {proc.returncode}"
            logger.warning("pkexec udev rule install failed: %s", err)
            if parent:
                QMessageBox.warning(
                    parent,
                    "Installation Failed",
                    f"Could not install udev rules:\n\n{err}"
                )
            return False

    except subprocess.TimeoutExpired:
        logger.warning("pkexec udev installation timed out")
        return False
    except Exception as e:
        logger.exception("Error executing pkexec udev installation")
        if parent:
            QMessageBox.critical(parent, "Error", f"Failed to execute pkexec:\n{e}")
        return False
