# OSPF Adjacency Test Suite — Scoped: A1M, D2B
# Run: pytest output/pytest/test_ospf_adjacency_A1M_D2B.py --junitxml=output/pytest/results.xml
#
# Generated: 2026-03-30
# Intent source: data/INTENT.json
# Pair: A1M (MikroTik RouterOS) <-> D2B (Aruba AOS-CX), Area 1 (stub)

import re
import yaml
import pytest

SPEC_PATH = "output/spec/ospf_adjacency_A1M_D2B.yaml"


def load_spec():
    """Load the YAML test specification."""
    with open(SPEC_PATH, "r") as f:
        return yaml.safe_load(f)


SPEC = load_spec()
ALL_TESTS = SPEC["tests"]


def get_tests_by_criterion(criterion_id):
    """Return test entries matching a specific criterion ID."""
    return [t for t in ALL_TESTS if t["criterion"] == criterion_id]


# ---------------------------------------------------------------------------
# Helpers — output parsing per cli_style
# ---------------------------------------------------------------------------

def parse_interface_status(output, interface, cli_style):
    """Extract line protocol status for an interface from show output."""
    if cli_style == "routeros":
        # /interface print brief without-paging
        # Columns: Flags, Name, Type, MTU, L2MTU, ...
        for line in output.splitlines():
            if interface in line:
                # RouterOS flags: R = running (up), D = dynamic, S = slave
                # If 'R' flag is present, interface is up
                if "R" in line.split(interface)[0]:
                    return "up"
                return "down"
    elif cli_style == "aos":
        # show interface brief
        for line in output.splitlines():
            if interface in line:
                if "up" in line.lower():
                    return "up"
                return "down"
    return None


def parse_neighbor_table(output, cli_style):
    """Parse OSPF neighbor output into a list of dicts with rid/state keys."""
    neighbors = []
    if cli_style == "routeros":
        # /routing ospf neighbor print detail without-paging
        # Each neighbor block has fields like: router-id=x.x.x.x state="Full"
        current = {}
        for line in output.splitlines():
            line = line.strip()
            if "router-id=" in line:
                rid_match = re.search(r"router-id=([\d.]+)", line)
                if rid_match:
                    current["rid"] = rid_match.group(1)
            if "state=" in line:
                state_match = re.search(r'state="?(\w+)"?', line)
                if state_match:
                    current["state"] = state_match.group(1).upper()
            if current.get("rid") and current.get("state"):
                neighbors.append(current)
                current = {}
    elif cli_style == "aos":
        # show ip ospf neighbors
        # Typical columns: Neighbor ID, Priority, State, Dead Time, Address, Interface
        for line in output.splitlines():
            parts = line.split()
            if len(parts) >= 4:
                rid_match = re.match(r"\d+\.\d+\.\d+\.\d+", parts[0])
                if rid_match:
                    state_raw = parts[2] if len(parts) > 2 else ""
                    # State may be "FULL/DR" or "FULL/BDR" — extract base state
                    state = state_raw.split("/")[0].upper()
                    neighbors.append({"rid": parts[0], "state": state})
    return neighbors


def parse_ospf_interface(output, interface, field, cli_style):
    """Extract a field value from OSPF interface output for a given interface."""
    if cli_style == "routeros":
        # /routing ospf interface print detail without-paging
        # Block per interface with key=value pairs
        in_block = False
        for line in output.splitlines():
            if interface in line:
                in_block = True
            if in_block:
                if field == "area_id":
                    m = re.search(r"area=([\w.\-]+)", line)
                    if m:
                        return m.group(1)
                elif field == "hello_interval":
                    m = re.search(r"hello-interval=([\d]+)", line)
                    if m:
                        return m.group(1)
                elif field == "dead_interval":
                    m = re.search(r"dead-interval=([\d]+)", line)
                    if m:
                        return m.group(1)
            # End of block detection — blank line or next entry
            if in_block and line.strip() == "":
                break
    elif cli_style == "aos":
        # show ip ospf interface
        in_block = False
        for line in output.splitlines():
            if interface in line:
                in_block = True
            if in_block:
                if field == "area_id":
                    m = re.search(r"[Aa]rea\s*(?:[Ii][Dd])?\s*[:=]?\s*([\d.]+)", line)
                    if m:
                        return m.group(1)
                elif field == "hello_interval":
                    m = re.search(r"[Hh]ello\s*[Ii]nterval\s*[:=]?\s*(\d+)", line)
                    if m:
                        return m.group(1)
                elif field == "dead_interval":
                    m = re.search(r"[Dd]ead\s*[Ii]nterval\s*[:=]?\s*(\d+)", line)
                    if m:
                        return m.group(1)
            if in_block and line.strip() == "":
                break
    return None


def parse_area_type(output, interface, cli_style):
    """Extract area type (normal/stub/nssa) for the area covering the given interface."""
    if cli_style == "routeros":
        # /routing ospf area print detail without-paging
        # Look for type= in area blocks
        for line in output.splitlines():
            if "type=" in line.lower():
                m = re.search(r"type=(\w+)", line, re.IGNORECASE)
                if m:
                    return m.group(1).lower()
    elif cli_style == "aos":
        # show ip ospf — look for area section with stub indication
        for line in output.splitlines():
            if "stub" in line.lower():
                return "stub"
            if "nssa" in line.lower():
                return "nssa"
    return "normal"


def parse_mtu(output, interface, cli_style):
    """Extract MTU value for an interface."""
    if cli_style == "routeros":
        # /interface print brief without-paging
        for line in output.splitlines():
            if interface in line:
                m = re.search(r"\b(\d{3,5})\b", line)
                if m:
                    return m.group(1)
    elif cli_style == "aos":
        # show interface brief
        for line in output.splitlines():
            if interface in line:
                m = re.search(r"\b(\d{3,5})\b", line)
                if m:
                    return m.group(1)
    return None


def parse_router_id(output, cli_style):
    """Extract OSPF router ID from process-level output."""
    if cli_style == "routeros":
        # /routing ospf instance print detail without-paging
        m = re.search(r"router-id=([\d.]+)", output)
        if m:
            return m.group(1)
    elif cli_style == "aos":
        # show ip ospf
        m = re.search(r"[Rr]outer\s*[Ii][Dd]\s*[:=]?\s*([\d.]+)", output)
        if m:
            return m.group(1)
    return None


# ---------------------------------------------------------------------------
# ADJ-01  Interface Up
# ---------------------------------------------------------------------------
class TestADJ01InterfaceUp:
    """ADJ-01: Verify interface line protocol is up. RFC 2328 section 9.1."""

    @pytest.mark.parametrize(
        "test_entry",
        get_tests_by_criterion("ADJ-01"),
        ids=[t["id"] for t in get_tests_by_criterion("ADJ-01")],
    )
    def test_interface_up(self, device_conn, test_entry):
        """[ADJ-01] Interface line protocol must be up for OSPF adjacency.

        RFC 2328 section 9.1 — An interface must be operational before OSPF
        can form adjacencies over it.
        """
        dev = test_entry["device"]
        conn = device_conn[dev["name"]]
        output = conn.send_command(test_entry["query"]["ssh_cli"]).result

        iface = test_entry["assertion"]["match_by"]["interface"]
        status = parse_interface_status(output, iface, dev["cli_style"])

        assert status == test_entry["assertion"]["expected"], (
            f"Interface {iface} on {dev['name']} line protocol is '{status}', "
            f"expected '{test_entry['assertion']['expected']}'"
        )


# ---------------------------------------------------------------------------
# ADJ-02  Neighbor Presence
# ---------------------------------------------------------------------------
class TestADJ02NeighborPresence:
    """ADJ-02: Verify OSPF neighbor is present. RFC 2328 section 10.1."""

    @pytest.mark.parametrize(
        "test_entry",
        get_tests_by_criterion("ADJ-02"),
        ids=[t["id"] for t in get_tests_by_criterion("ADJ-02")],
    )
    def test_neighbor_presence(self, device_conn, test_entry):
        """[ADJ-02] The peer router ID must appear in the OSPF neighbor table.

        RFC 2328 section 10.1 — Neighbor discovery via Hello protocol.
        """
        dev = test_entry["device"]
        conn = device_conn[dev["name"]]
        output = conn.send_command(test_entry["query"]["ssh_cli"]).result

        expected_rid = test_entry["assertion"]["expected"]
        neighbors = parse_neighbor_table(output, dev["cli_style"])
        found_rids = [n["rid"] for n in neighbors]

        assert expected_rid in found_rids, (
            f"Neighbor RID {expected_rid} not found in {dev['name']} neighbor table. "
            f"Found: {found_rids}"
        )


# ---------------------------------------------------------------------------
# ADJ-03  State FULL
# ---------------------------------------------------------------------------
class TestADJ03StateFull:
    """ADJ-03: Verify OSPF adjacency state is FULL. RFC 2328 section 10.1."""

    @pytest.mark.parametrize(
        "test_entry",
        get_tests_by_criterion("ADJ-03"),
        ids=[t["id"] for t in get_tests_by_criterion("ADJ-03")],
    )
    def test_state_full(self, device_conn, test_entry):
        """[ADJ-03] Adjacency must reach FULL state for database synchronization.

        RFC 2328 section 10.1 — FULL state indicates databases are synchronized.
        """
        dev = test_entry["device"]
        conn = device_conn[dev["name"]]
        output = conn.send_command(test_entry["query"]["ssh_cli"]).result

        peer_rid = test_entry["assertion"]["match_by"]["router_id"]
        neighbors = parse_neighbor_table(output, dev["cli_style"])

        neighbor = next((n for n in neighbors if n["rid"] == peer_rid), None)
        assert neighbor is not None, (
            f"Neighbor {peer_rid} not found on {dev['name']}"
        )
        assert neighbor["state"] == test_entry["assertion"]["expected"], (
            f"Neighbor {peer_rid} on {dev['name']} state is '{neighbor['state']}', "
            f"expected '{test_entry['assertion']['expected']}'"
        )


# ---------------------------------------------------------------------------
# ADJ-04  Area ID Match
# ---------------------------------------------------------------------------
class TestADJ04AreaMatch:
    """ADJ-04: Verify OSPF interface area assignment. RFC 2328 section 10.5."""

    @pytest.mark.parametrize(
        "test_entry",
        get_tests_by_criterion("ADJ-04"),
        ids=[t["id"] for t in get_tests_by_criterion("ADJ-04")],
    )
    def test_area_match(self, device_conn, test_entry):
        """[ADJ-04] Interface must be assigned to the correct OSPF area.

        RFC 2328 section 10.5 — Area ID in Hello packets must match for
        adjacency to form.
        """
        dev = test_entry["device"]
        conn = device_conn[dev["name"]]
        output = conn.send_command(test_entry["query"]["ssh_cli"]).result

        iface = test_entry["assertion"]["match_by"]["interface"]
        area_id = parse_ospf_interface(output, iface, "area_id", dev["cli_style"])

        assert area_id == test_entry["assertion"]["expected"], (
            f"Interface {iface} on {dev['name']} area is '{area_id}', "
            f"expected '{test_entry['assertion']['expected']}'"
        )


# ---------------------------------------------------------------------------
# ADJ-05  Timer Match
# ---------------------------------------------------------------------------
class TestADJ05TimerMatch:
    """ADJ-05: Verify OSPF hello/dead interval timers. RFC 2328 section 10.5."""

    @pytest.mark.parametrize(
        "test_entry",
        get_tests_by_criterion("ADJ-05"),
        ids=[t["id"] for t in get_tests_by_criterion("ADJ-05")],
    )
    def test_timer_match(self, device_conn, test_entry):
        """[ADJ-05] Hello and dead intervals must match on both sides of a link.

        RFC 2328 section 10.5 — Mismatched timers prevent adjacency formation.
        """
        dev = test_entry["device"]
        conn = device_conn[dev["name"]]
        output = conn.send_command(test_entry["query"]["ssh_cli"]).result

        iface = test_entry["assertion"]["match_by"]["interface"]
        field = test_entry["assertion"]["field"]
        value = parse_ospf_interface(output, iface, field, dev["cli_style"])

        assert value == test_entry["assertion"]["expected"], (
            f"{field} on {iface} ({dev['name']}) is '{value}', "
            f"expected '{test_entry['assertion']['expected']}'"
        )


# ---------------------------------------------------------------------------
# ADJ-06  Stub Agreement
# ---------------------------------------------------------------------------
class TestADJ06StubAgreement:
    """ADJ-06: Verify stub area agreement. RFC 2328 section 11."""

    @pytest.mark.parametrize(
        "test_entry",
        get_tests_by_criterion("ADJ-06"),
        ids=[t["id"] for t in get_tests_by_criterion("ADJ-06")],
    )
    def test_stub_agreement(self, device_conn, test_entry):
        """[ADJ-06] Both routers must agree on stub area configuration.

        RFC 2328 section 11 — The E-bit in Hello options must match;
        stub areas set E-bit to 0.
        """
        dev = test_entry["device"]
        conn = device_conn[dev["name"]]
        output = conn.send_command(test_entry["query"]["ssh_cli"]).result

        iface = test_entry["assertion"]["match_by"]["interface"]
        area_type = parse_area_type(output, iface, dev["cli_style"])

        assert area_type == test_entry["assertion"]["expected"], (
            f"Area type for {iface} on {dev['name']} is '{area_type}', "
            f"expected '{test_entry['assertion']['expected']}'"
        )


# ---------------------------------------------------------------------------
# ADJ-07  MTU Match
# ---------------------------------------------------------------------------
class TestADJ07MtuMatch:
    """ADJ-07: Verify interface MTU consistency. RFC 2328 section 10.6."""

    @pytest.mark.parametrize(
        "test_entry",
        get_tests_by_criterion("ADJ-07"),
        ids=[t["id"] for t in get_tests_by_criterion("ADJ-07")],
    )
    def test_mtu_match(self, device_conn, test_entry):
        """[ADJ-07] Interface MTU must match across the link to avoid DD rejection.

        RFC 2328 section 10.6 — MTU is included in Database Description packets;
        if received MTU exceeds local MTU, the DD packet is rejected.
        """
        dev = test_entry["device"]
        conn = device_conn[dev["name"]]
        output = conn.send_command(test_entry["query"]["ssh_cli"]).result

        iface = test_entry["assertion"]["match_by"]["interface"]
        mtu = parse_mtu(output, iface, dev["cli_style"])

        assert mtu == test_entry["assertion"]["expected"], (
            f"MTU on {iface} ({dev['name']}) is '{mtu}', "
            f"expected '{test_entry['assertion']['expected']}'"
        )


# ---------------------------------------------------------------------------
# ADJ-08  Router ID Unique
# ---------------------------------------------------------------------------
class TestADJ08RouterIdUnique:
    """ADJ-08: Verify OSPF router ID matches intent. RFC 2328 appendix C.1."""

    @pytest.mark.parametrize(
        "test_entry",
        get_tests_by_criterion("ADJ-08"),
        ids=[t["id"] for t in get_tests_by_criterion("ADJ-08")],
    )
    def test_router_id_unique(self, device_conn, test_entry):
        """[ADJ-08] Router ID must match the intended value and be unique.

        RFC 2328 appendix C.1 — Duplicate Router IDs cause routing anomalies
        including adjacency flapping and LSDB corruption.
        """
        dev = test_entry["device"]
        conn = device_conn[dev["name"]]
        output = conn.send_command(test_entry["query"]["ssh_cli"]).result

        rid = parse_router_id(output, dev["cli_style"])

        assert rid == test_entry["assertion"]["expected"], (
            f"Router ID on {dev['name']} is '{rid}', "
            f"expected '{test_entry['assertion']['expected']}'"
        )
