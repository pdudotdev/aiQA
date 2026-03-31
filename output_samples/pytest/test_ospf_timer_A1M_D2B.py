"""OSPF timer mismatch tests for A1M ↔ D2B.

Cross-vendor pair: MikroTik RouterOS (A1M) ↔ Aruba AOS-CX (D2B).
Both directions tested per QC-8.

RFC 2328 §10.5 — Hello and dead timers MUST match for adjacency to form.
"""

import time
import yaml
import pytest
from pathlib import Path
from conftest import register_rollback, deregister_rollback, _poll_until

SPEC_PATH = Path(__file__).resolve().parent.parent / "spec" / "ospf_timer_A1M_D2B.yaml"


def load_tests():
    with open(SPEC_PATH) as f:
        spec = yaml.safe_load(f)
    return spec["tests"]


def parse_neighbor_state(output, router_id):
    """Extract neighbor state for a given router ID from show output."""
    for line in output.splitlines():
        if router_id in line:
            parts = line.split()
            for i, part in enumerate(parts):
                if part == router_id or part.strip(",") == router_id:
                    # State is typically the first or a known-position field
                    # For AOS-CX: show ip ospf neighbors → RID Priority State ...
                    # For RouterOS: print detail → state=full
                    break
            # AOS-CX format: "RID  Priority  State  Dead-Time  Address  Interface"
            if len(parts) >= 3:
                return parts[2] if parts[0] == router_id else None
    return None


def parse_routeros_neighbor_state(output, router_id):
    """Parse RouterOS neighbor detail output for a specific router ID."""
    current_rid = None
    current_state = None
    for line in output.splitlines():
        line = line.strip()
        if "router-id=" in line:
            for token in line.split():
                if token.startswith("router-id="):
                    current_rid = token.split("=", 1)[1]
        if "state=" in line:
            for token in line.split():
                if token.startswith("state="):
                    current_state = token.split("=", 1)[1].strip('"')
        if current_rid == router_id and current_state:
            return current_state
    return None


TEST_DATA = load_tests()


@pytest.mark.parametrize(
    "test_entry",
    TEST_DATA,
    ids=[t["id"] for t in TEST_DATA],
)
def test_ospf_timer_mismatch(connections, test_entry):
    """[{criterion}] {description} — {rfc}"""
    setup = test_entry["setup"]
    teardown = test_entry["teardown"]
    wait = test_entry["wait"]
    query = test_entry["query"]
    assertion = test_entry["assertion"]

    setup_device = setup["target"]
    verify_device = test_entry["device"]["name"]
    peer_rid = assertion["match_by"]["router_id"]

    setup_conn = connections[setup_device]
    verify_conn = connections[verify_device]

    is_routeros_verify = test_entry["device"]["cli_style"] == "routeros"

    # Pre-flight: verify baseline FULL adjacency
    baseline_out = verify_conn.send_command(setup["snapshot_cli"]).result
    if is_routeros_verify:
        baseline_state = parse_routeros_neighbor_state(baseline_out, peer_rid)
    else:
        baseline_state = parse_neighbor_state(baseline_out, peer_rid)
    assert baseline_state == setup["snapshot_expected"], (
        f"Pre-flight failed on {verify_device}: "
        f"neighbor {peer_rid} state={baseline_state!r}, expected={setup['snapshot_expected']!r}"
    )

    register_rollback(setup_conn, teardown["ssh_cli"])
    try:
        # Setup: configure timer mismatch (config mode)
        setup_conn.send_configs(setup["ssh_cli"].split("\n"))

        # Wait for convergence
        time.sleep(wait["seconds"])

        # Verify: adjacency should NOT be FULL
        result_out = verify_conn.send_command(query["ssh_cli"]).result
        if is_routeros_verify:
            actual_state = parse_routeros_neighbor_state(result_out, peer_rid)
        else:
            actual_state = parse_neighbor_state(result_out, peer_rid)

        assert actual_state != assertion["expected"], (
            f"[{test_entry['criterion']}] {test_entry['description']}: "
            f"neighbor {peer_rid} state={actual_state!r}, expected NOT {assertion['expected']!r}"
        )
    finally:
        # Teardown: rollback config (config mode)
        setup_conn.send_configs(teardown["ssh_cli"].split("\n"))

        # Wait for adjacency to restore
        time.sleep(wait["seconds"])

        # Verify rollback: adjacency should be FULL again
        verify_out = verify_conn.send_command(teardown["verify_cli"]).result
        if is_routeros_verify:
            restored_state = parse_routeros_neighbor_state(verify_out, peer_rid)
        else:
            restored_state = parse_neighbor_state(verify_out, peer_rid)
        assert restored_state == teardown["verify_expected"], (
            f"ROLLBACK FAILED on {verify_device}: "
            f"neighbor {peer_rid} state={restored_state!r}, expected={teardown['verify_expected']!r}"
        )
        deregister_rollback(setup_conn, teardown["ssh_cli"])
