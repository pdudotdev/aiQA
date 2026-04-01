# YAML Test Spec Schema

Canonical test specification format. Read this before generating the YAML spec.
Renderer guidance (pytest/Ansible) is in `.claude/spec-renderers.md` — read that before rendering.

---

## Test Model

All tests are active: configure a condition → wait → check the result → teardown (revert). Every test entry must have `setup`, `wait`, and `teardown` blocks.

---

## YAML Spec Schema

Fields marked `# optional` may be omitted.

```yaml
metadata:
  skill: <skill-name>             # e.g., ospf_timer, bgp_peering
  protocol: <protocol>            # e.g., ospf, bgp, eigrp
  generated: <ISO-8601 timestamp>
  intent_source: data/INTENT.json
  scope: <all | device-filtered>  # "all" or comma-separated device names
  pair_count: <N>
  test_count: <N>

tests:
  - id: <skill>_<criterion>_<setupDevice>_<verifyDevice>   # setup target first, verify target second (encodes direction)
    criterion: <criterion_id>     # e.g., TMISMATCH-01, ADJ-01
    rfc: "<RFC reference>"        # mandatory — e.g., "RFC 2328 §10.5"
    description: "<human-readable one-liner>"
    device:                       # the setup target — where the config change is applied
      name: <deviceA>
      host: <ip-address>
      platform: <platform>        # cisco_iosxe | arista_eos | juniper_junos | aruba_aoscx | mikrotik_routeros | vyos
      cli_style: <cli_style>      # ios | eos | junos | aos | routeros | vyos
      interface: <interface>      # optional
      ip: <ip>                    # optional
    peer:                         # optional — the verify target. ALL fields below describe the PEER device itself, never the setup device.
      name: <deviceB>
      host: <ip-address>
      platform: <platform>
      cli_style: <cli_style>
      rid: <router-id>            # optional — the peer device's own router_id from INTENT.json
      interface: <interface>      # optional
      ip: <ip>                    # optional
    context:                      # protocol-specific topology fields
      area: <area_id>             # OSPF: e.g., 0, 1
      area_type: <type>           # OSPF: normal | stub | nssa
      # extensible per protocol
    query:
      ssh_cli: "<vendor-specific show command>"  # MUST be scoped to the specific test target (interface, neighbor, process)
    assertion:
      type: <assertion_type>
      field: <what to check>
      expected: <expected_value>  # never null or "any"
      match_by:                   # optional — omit for process-level checks
        router_id: <rid>
        interface: <iface>

    # All three blocks are mandatory for every test entry
    setup:
      target: <device-name>       # device to configure
      ssh_cli: "<config command>"   # MUST include the full config-mode path: submode navigation (interface X, router ospf N) + the command. NEVER include terminal-level transitions (configure terminal, conf t, exit, end). Example: "interface Ethernet0/1\nip ospf hello-interval 15" — NOT just "ip ospf hello-interval 15".
      snapshot_cli: "<show command>"  # MUST be scoped to the specific interface, neighbor, or process being tested
      snapshot_field: <field>
      snapshot_expected: "<value>" # from INTENT.json — never guessed
    wait:
      type: <convergence|fixed|poll>
      seconds: <N>
      poll_cli: "<show command>"  # optional, used with type: poll
      poll_condition: "<condition>"  # optional
      # IMPLEMENTATION NOTE: _poll_until() MUST exit with a timeout exception after
      # 'seconds' have elapsed. Polling interval is implementation-defined (default 5s).
    teardown:
      ssh_cli: "<rollback command>"  # same rules as setup.ssh_cli: full config-mode path with submode navigation, no terminal-level transitions
      verify_cli: "<show command>"  # MUST equal setup.snapshot_cli
      verify_field: <field>         # MUST equal setup.snapshot_field
      verify_expected: "<value>"    # MUST equal setup.snapshot_expected
```

---

## ID Naming Convention

`<skill>_<criterion>_<setupDevice>_<verifyDevice>` — encodes test direction (setup target first, verify target second).
Per-device criteria: `<skill>_<criterion>_<device>`.

For bidirectional tests (QC-8), each direction gets its own ID: `ospf_timer_TMISMATCH-01_A1M_D2B` (setup on A1M, verify on D2B) and `ospf_timer_TMISMATCH-01_D2B_A1M` (setup on D2B, verify on A1M).

Examples: `ospf_timer_TMISMATCH-01_A1M_D2B`, `ospf_timer_TMISMATCH-01_D2B_A1M`, `ospf_adj_ADJ-08_D1C`

---

## Schema Rules

1. Every test entry MUST have `setup`, `wait`, AND `teardown` — all three, always.
2. Teardown verification MUST re-check the same parameter that was changed: `teardown.verify_cli` MUST equal `setup.snapshot_cli`, `teardown.verify_field` MUST equal `setup.snapshot_field`, and `teardown.verify_expected` MUST equal `setup.snapshot_expected`.
3. `setup.snapshot_expected` MUST come from INTENT.json — never guessed.
4. Do NOT create separate test entries for teardown/rollback verification — verification that the rollback succeeded belongs inside the `teardown` block of the same entry, not as a standalone test.
