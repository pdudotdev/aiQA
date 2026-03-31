"""Shared fixtures for OSPF timer mismatch tests."""

import json
import pytest
from pathlib import Path
from scrapli import Scrapli

INTENT_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "INTENT.json"

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


@pytest.fixture(scope="session")
def intent():
    with open(INTENT_PATH) as f:
        return json.load(f)["routers"]


@pytest.fixture(scope="session")
def connections(intent):
    conns = {}
    for name, data in intent.items():
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
            conn.send_command(cmd)
        except Exception as e:
            print(f"[EMERGENCY ROLLBACK] {cmd}: {e}")
