"""OSPF timer mismatch tests — A1M (routeros) ↔ D2B (aos).

Criteria:
  TMISMATCH-01  Hello-interval mismatch → adjacency drops  (RFC 2328 §10.5)
  TMISMATCH-02  Dead-interval mismatch  → adjacency drops  (RFC 2328 §10.5)

Directions: both (cross-vendor pair).
"""

import time

import pytest
import yaml
from pathlib import Path

from conftest import (
    ALL_TEST_ENTRIES,
    COMMIT_PLATFORMS,
    parse_and_match,
    parse_field,
    register_rollback,
    deregister_rollback,
)

# Filter entries for this specific test file
_THIS_SPEC = Path(__file__).resolve().parent.parent / "spec" / "ospf_timer_A1M_D2B.yaml"
with open(_THIS_SPEC) as _f:
    _spec = yaml.safe_load(_f)
_TESTS = _spec["tests"]


@pytest.mark.parametrize(
    "test_entry",
    _TESTS,
    ids=[t["id"] for t in _TESTS],
)
def test_ospf_timer_mismatch(connections, test_entry):
    """Active test: configure timer mismatch → wait → verify adjacency drops → teardown.

    RFC 2328 §10.5 — Hello and dead timers MUST match on both sides of a
    link.  A mismatch causes the neighbor to reject Hello packets; the dead
    timer expires and the adjacency is torn down.
    """
    setup = test_entry["setup"]
    teardown = test_entry["teardown"]
    wait = test_entry["wait"]
    assertion = test_entry["assertion"]
    cli_style = test_entry["device"]["cli_style"]

    device_conn = connections[test_entry["device"]["name"]]
    peer_conn = connections[test_entry["peer"]["name"]]

    # --- Pre-flight: verify baseline ---
    out = device_conn.send_command(setup["snapshot_cli"])
    baseline = parse_field(out, setup["snapshot_field"])
    assert baseline == setup["snapshot_expected"], (
        f"Pre-flight failed on {test_entry['device']['name']}: "
        f"{setup['snapshot_field']}={baseline!r}, expected {setup['snapshot_expected']!r}"
    )

    register_rollback(device_conn, teardown["ssh_cli"], cli_style)
    try:
        # --- Setup: introduce timer mismatch ---
        device_conn.send_config_set(setup["ssh_cli"].split("\n"))
        if cli_style in COMMIT_PLATFORMS:
            device_conn.commit()

        # --- Wait for dead timer expiry ---
        time.sleep(wait["seconds"])

        # --- Assert: adjacency should NOT be Full ---
        result = peer_conn.send_command(test_entry["query"]["ssh_cli"])
        actual = parse_and_match(result, assertion, assertion.get("match_by"))

        if assertion["type"] == "not_equal":
            assert actual != assertion["expected"], (
                f"[{test_entry['criterion']}] {test_entry['device']['name']}→"
                f"{test_entry['peer']['name']}: neighbor state is still "
                f"{actual!r}, expected NOT {assertion['expected']!r}"
            )
        else:
            assert actual == assertion["expected"], (
                f"[{test_entry['criterion']}] expected {assertion['expected']!r}, "
                f"got {actual!r}"
            )

    finally:
        # --- Teardown: revert timer to default ---
        device_conn.send_config_set(teardown["ssh_cli"].split("\n"))
        if cli_style in COMMIT_PLATFORMS:
            device_conn.commit()

        # Wait for reconvergence
        time.sleep(wait["seconds"])

        # Verify rollback
        verify = device_conn.send_command(teardown["verify_cli"])
        restored = parse_field(verify, teardown["verify_field"])
        assert restored == teardown["verify_expected"], (
            f"ROLLBACK FAILED on {test_entry['device']['name']}: "
            f"{teardown['verify_field']}={restored!r}, expected {teardown['verify_expected']!r}"
        )
        deregister_rollback(device_conn, teardown["ssh_cli"], cli_style)
