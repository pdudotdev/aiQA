"""Shared fixtures for network test suites.

Loads all YAML specs from output/spec/, builds Netmiko connections
for referenced devices only, and provides rollback safety net.
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

# ---------------------------------------------------------------------------
# Rollback registry
# ---------------------------------------------------------------------------

_rollback_registry: list[tuple] = []


def register_rollback(conn, cmd, cli_style):
    _rollback_registry.append((conn, cmd, cli_style))


def deregister_rollback(conn, cmd, cli_style):
    try:
        _rollback_registry.remove((conn, cmd, cli_style))
    except ValueError:
        pass


@pytest.fixture(scope="session", autouse=True)
def emergency_rollback():
    yield
    for conn, cmd, cli_style in _rollback_registry:
        try:
            conn.send_config_set(cmd.split("\n"))
            if cli_style in COMMIT_PLATFORMS:
                conn.commit()
        except Exception as e:
            print(f"[EMERGENCY ROLLBACK] {cmd}: {e}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def parse_field(output: str, field: str) -> str:
    """Extract a field value from CLI output (key: value or key=value)."""
    for line in output.splitlines():
        line_stripped = line.strip()
        # key: value
        if f"{field}:" in line_stripped.lower() or f"{field} :" in line_stripped.lower():
            return line_stripped.split(":", 1)[1].strip().split()[0]
        # key=value (RouterOS)
        if f"{field}=" in line_stripped:
            part = line_stripped.split(f"{field}=", 1)[1]
            return part.split()[0].strip()
        # "field  value" tabular
        if field.lower() in line_stripped.lower():
            parts = line_stripped.split()
            for i, p in enumerate(parts):
                if field.lower() in p.lower() and i + 1 < len(parts):
                    return parts[i + 1]
    return ""


def parse_and_match(output: str, assertion: dict, match_by: dict | None) -> str:
    """Find the matching neighbor/entry and return the asserted field value.

    For 'not_equal' assertions, returns the field value (or '__ABSENT__' if
    the neighbor is not found). The caller checks equality/inequality.
    """
    field = assertion["field"]

    if not match_by:
        return parse_field(output, field)

    rid = match_by.get("router_id", "")
    # Find the block/line matching the router-id, then extract the field
    lines = output.splitlines()
    in_block = False
    for line in lines:
        if rid in line:
            in_block = True
        if in_block:
            val = _try_extract(line, field)
            if val:
                return val
            # If we hit an empty line or new entry, stop
            if in_block and line.strip() == "":
                break
    return "__ABSENT__"


def _try_extract(line: str, field: str) -> str | None:
    low = line.strip().lower()
    if field.lower() in low:
        parts = line.strip().split()
        for i, p in enumerate(parts):
            if field.lower() in p.lower() and i + 1 < len(parts):
                return parts[i + 1].rstrip(",")
        if ":" in line:
            return line.split(":", 1)[1].strip().split()[0]
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


# ---------------------------------------------------------------------------
# Spec loading
# ---------------------------------------------------------------------------

def _load_all_specs() -> list[dict]:
    """Load all YAML specs and return flattened test entries."""
    entries = []
    for spec_file in sorted(SPEC_DIR.glob("*.yaml")):
        with open(spec_file) as f:
            spec = yaml.safe_load(f)
        for t in spec.get("tests", []):
            entries.append(t)
    return entries


def _collect_device_names(entries: list[dict]) -> set[str]:
    names = set()
    for t in entries:
        names.add(t["device"]["name"])
        if "peer" in t:
            names.add(t["peer"]["name"])
    return names


def _build_device_info(entries: list[dict]) -> dict:
    """Map device name → {host, cli_style} from spec entries."""
    info = {}
    for t in entries:
        d = t["device"]
        info[d["name"]] = {"host": d["host"], "cli_style": d["cli_style"]}
        if "peer" in t:
            p = t["peer"]
            info[p["name"]] = {"host": p["host"], "cli_style": p["cli_style"]}
    return info


ALL_TEST_ENTRIES = _load_all_specs()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def connections():
    """Open Netmiko connections to all devices referenced in specs."""
    device_info = _build_device_info(ALL_TEST_ENTRIES)
    conns = {}
    for name, info in device_info.items():
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


# ---------------------------------------------------------------------------
# JUnit XML auto-configuration
# ---------------------------------------------------------------------------

def pytest_configure(config):
    """Auto-enable JUnit XML output if not specified on command line."""
    if not config.option.xmlpath:
        config.option.xmlpath = str(Path(__file__).parent / "results.xml")
