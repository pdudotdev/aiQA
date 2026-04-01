"""OSPF timer mismatch tests — A1M (routeros) <-> D2B (aos).

Criteria:
  TMISMATCH-01  Hello interval mismatch (RFC 2328 Section 10.5)
  TMISMATCH-02  Dead interval mismatch  (RFC 2328 Section 10.5)

Both directions tested (cross-vendor pair).
"""

import time
from pathlib import Path

import pytest
import yaml

from conftest import (
    COMMIT_PLATFORMS,
    parse_and_match,
    parse_field,
    register_rollback,
    deregister_rollback,
    _poll_until,
)


SPEC_FILE = Path(__file__).resolve().parent.parent / "spec" / "ospf_timer_A1M_D2B.yaml"


def _load_tests():
    with open(SPEC_FILE) as f:
        doc = yaml.safe_load(f)
    return doc["tests"]


@pytest.mark.parametrize("test_entry", _load_tests(), ids=lambda t: t["id"])
def test_ospf_timer_mismatch(connections, test_entry):
    """Active test: configure timer mismatch -> wait -> verify adjacency drops -> rollback.

    Criterion: {criterion}
    RFC: {rfc}
    Description: {description}
    """
    setup = test_entry["setup"]
    teardown = test_entry["teardown"]
    wait = test_entry["wait"]
    cli_style = test_entry["device"]["cli_style"]

    device_conn = connections[test_entry["device"]["name"]]
    peer_conn = connections[test_entry["peer"]["name"]]

    # ── Pre-flight: verify baseline ──────────────────────────────────────
    out = device_conn.send_command(setup["snapshot_cli"])
    baseline = parse_field(out, setup["snapshot_field"])
    assert baseline == setup["snapshot_expected"], (
        f"Pre-flight failed on {test_entry['device']['name']}: "
        f"{setup['snapshot_field']}={baseline!r}, expected {setup['snapshot_expected']!r}"
    )

    register_rollback(device_conn, teardown["ssh_cli"])
    try:
        # ── Setup: apply mismatched timer ────────────────────────────────
        device_conn.send_config_set(setup["ssh_cli"].split("\n"))
        if cli_style in COMMIT_PLATFORMS:
            device_conn.commit()

        # ── Wait for dead timer expiry ───────────────────────────────────
        if wait["type"] in ("convergence", "fixed"):
            time.sleep(wait["seconds"])
        elif wait["type"] == "poll":
            _poll_until(peer_conn, wait)

        # ── Assert: adjacency should NOT be Full ─────────────────────────
        result = peer_conn.send_command(test_entry["query"]["ssh_cli"])
        actual = parse_and_match(
            result,
            test_entry["assertion"],
            test_entry["assertion"].get("match_by"),
        )
        assertion_type = test_entry["assertion"]["type"]
        expected = test_entry["assertion"]["expected"]

        if assertion_type == "not_equal":
            assert actual != expected, (
                f"[{test_entry['criterion']}] {test_entry['assertion']['field']} "
                f"is still {actual!r} on {test_entry['peer']['name']} — "
                f"expected it to change from {expected!r} after timer mismatch"
            )
        else:
            assert actual == expected, (
                f"[{test_entry['criterion']}] {test_entry['assertion']['field']}="
                f"{actual!r} on {test_entry['peer']['name']}, expected {expected!r}"
            )

    finally:
        # ── Teardown: revert timer to default ────────────────────────────
        device_conn.send_config_set(teardown["ssh_cli"].split("\n"))
        if cli_style in COMMIT_PLATFORMS:
            device_conn.commit()

        # Wait for reconvergence
        time.sleep(wait["seconds"])

        # Verify rollback
        verify = device_conn.send_command(setup["snapshot_cli"])
        restored = parse_field(verify, setup["snapshot_field"])
        assert restored == setup["snapshot_expected"], (
            f"ROLLBACK FAILED on {test_entry['device']['name']}: "
            f"{setup['snapshot_field']}={restored!r}, expected {setup['snapshot_expected']!r}"
        )
        deregister_rollback(device_conn, teardown["ssh_cli"])
