"""Shared fixtures for network test suites.

Loads all YAML specs from the spec directory, connects only to devices
referenced in those specs, and provides session-scoped rollback safety.
"""

import time
from pathlib import Path

import pytest
import yaml
from netmiko import ConnectHandler


PLATFORM_MAP = {
    "ios": "cisco_ios",
    "eos": "arista_eos",
    "junos": "juniper_junos",
    "aos": "aruba_aoscx",
    "routeros": "mikrotik_routeros",
    "vyos": "vyos",
}
COMMIT_PLATFORMS = {"junos", "vyos"}

SPEC_DIR = Path(__file__).resolve().parent.parent / "spec"

# ── Rollback registry ────────────────────────────────────────────────────────

_rollback_registry: list[tuple] = []


def register_rollback(conn, cmd):
    _rollback_registry.append((conn, cmd))


def deregister_rollback(conn, cmd):
    try:
        _rollback_registry.remove((conn, cmd))
    except ValueError:
        pass


@pytest.fixture(scope="session", autouse=True)
def emergency_rollback():
    yield
    for conn, cmd in _rollback_registry:
        try:
            conn.send_config_set(cmd.split("\n"))
        except Exception as e:
            print(f"[EMERGENCY ROLLBACK] {cmd}: {e}")


# ── Spec loading ─────────────────────────────────────────────────────────────

def _load_all_specs():
    specs = []
    for f in sorted(SPEC_DIR.glob("*.yaml")):
        with open(f) as fh:
            doc = yaml.safe_load(fh)
        if doc and "tests" in doc:
            specs.extend(doc["tests"])
    return specs


ALL_TESTS = _load_all_specs()


def _referenced_devices():
    devices = {}
    for t in ALL_TESTS:
        d = t["device"]
        devices[d["name"]] = d
        if "peer" in t:
            p = t["peer"]
            devices[p["name"]] = p
    return devices


# ── Connection fixtures ──────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def connections():
    conns = {}
    for name, info in _referenced_devices().items():
        device_type = PLATFORM_MAP[info["cli_style"]]
        conn = ConnectHandler(
            device_type=device_type,
            host=info["host"],
            username="admin",
            password="admin",
        )
        conns[name] = conn
    yield conns
    for conn in conns.values():
        try:
            conn.disconnect()
        except Exception:
            pass


# ── Helpers ──────────────────────────────────────────────────────────────────

def parse_field(output: str, field: str) -> str:
    """Extract a field value from show command output.

    Handles both key: value and key=value formats, plus RouterOS
    detail output (key: value with leading whitespace).
    """
    for line in output.splitlines():
        stripped = line.strip()
        # key: value
        if f"{field}:" in stripped:
            return stripped.split(f"{field}:")[-1].strip()
        # key=value (RouterOS terse)
        if f"{field}=" in stripped:
            segment = stripped.split(f"{field}=")[-1]
            return segment.split()[0].strip()
    return ""


def parse_and_match(output: str, assertion: dict, match_by: dict | None) -> str:
    """Parse show output, optionally filter by match_by criteria, return field value."""
    field = assertion["field"]
    if not match_by:
        return parse_field(output, field)

    rid = match_by.get("router_id", "")
    block = _find_neighbor_block(output, rid)
    if block is None:
        return ""
    return parse_field(block, field)


def _find_neighbor_block(output: str, router_id: str) -> str | None:
    """Find the text block for a specific neighbor by router ID."""
    lines = output.splitlines()
    for i, line in enumerate(lines):
        if router_id in line:
            # Gather contiguous block (until next blank line or next neighbor)
            block_lines = [line]
            for j in range(i + 1, len(lines)):
                if lines[j].strip() == "" or (
                    lines[j][0:1].isalnum() and j > i + 1
                ):
                    break
                block_lines.append(lines[j])
            return "\n".join(block_lines)
    return None


def _poll_until(conn, wait_spec: dict):
    """Poll a show command until condition is met or timeout expires."""
    timeout = wait_spec["seconds"]
    interval = 5
    cli = wait_spec["poll_cli"]
    condition = wait_spec["poll_condition"]
    deadline = time.time() + timeout
    while time.time() < deadline:
        out = conn.send_command(cli)
        if condition in out:
            return
        time.sleep(interval)
    raise TimeoutError(f"Poll condition {condition!r} not met after {timeout}s")


# ── JUnit XML auto-configuration ────────────────────────────────────────────

def pytest_configure(config):
    """Auto-enable JUnit XML output if not specified on command line."""
    if not config.option.xmlpath:
        config.option.xmlpath = str(Path(__file__).parent / "results.xml")
