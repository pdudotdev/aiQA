"""Shared fixtures for OSPF timer mismatch tests."""

import json
import time
import yaml
import pytest
from pathlib import Path
from scrapli import Scrapli

INTENT_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "INTENT.json"
SPEC_DIR = Path(__file__).resolve().parent.parent / "spec"

PLATFORM_MAP = {
    "ios": "cisco_iosxe",
    "eos": "arista_eos",
    "junos": "juniper_junos",
    "aos": "aruba_aoscx",
    "routeros": "mikrotik_routeros",
    "vyos": "linux",
}

_rollback_registry = []


def register_rollback(conn, cmd):
    _rollback_registry.append((conn, cmd))


def deregister_rollback(conn, cmd):
    _rollback_registry.remove((conn, cmd))


def _poll_until(conn, wait_spec):
    """Poll a show command until condition is met or timeout expires."""
    timeout = wait_spec["seconds"]
    interval = 5
    cli = wait_spec["poll_cli"]
    condition = wait_spec["poll_condition"]
    deadline = time.time() + timeout
    while time.time() < deadline:
        out = conn.send_command(cli).result
        if condition in out:
            return
        time.sleep(interval)
    raise TimeoutError(f"Poll condition {condition!r} not met after {timeout}s")


def _devices_in_specs():
    """Extract unique device names from all YAML specs in the spec directory."""
    devices = set()
    for spec_file in SPEC_DIR.glob("*.yaml"):
        with open(spec_file) as f:
            spec = yaml.safe_load(f)
        for test in spec.get("tests", []):
            devices.add(test["device"]["name"])
            if "peer" in test:
                devices.add(test["peer"]["name"])
            if "setup" in test and "target" in test["setup"]:
                devices.add(test["setup"]["target"])
    return devices


@pytest.fixture(scope="session")
def intent():
    with open(INTENT_PATH) as f:
        return json.load(f)["routers"]


@pytest.fixture(scope="session")
def connections(intent):
    needed = _devices_in_specs()
    conns = {}
    for name, data in intent.items():
        if name not in needed:
            continue
        cli_style = data["cli_style"]
        platform = PLATFORM_MAP[cli_style]
        conn = Scrapli(
            host=data["host"],
            auth_username="admin",
            auth_password="admin",
            auth_strict_key=False,
            platform=platform,
            transport="asyncssh",
        )
        conn.open()
        conns[name] = conn
    yield conns
    for conn in conns.values():
        try:
            conn.close()
        except Exception:
            pass


@pytest.fixture(scope="session", autouse=True)
def emergency_rollback():
    yield
    for conn, cmd in _rollback_registry:
        try:
            conn.send_configs(cmd.split("\n"))
        except Exception as e:
            print(f"[EMERGENCY ROLLBACK] {cmd}: {e}")
