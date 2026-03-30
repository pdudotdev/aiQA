# Shared YAML Test Spec Schema + Renderer Guidance

This document defines the canonical YAML test specification format used by all aiQA skills, and provides renderer guidance for pytest and Ansible artifacts.

---

## YAML Spec Schema

All skills produce YAML files following this schema. Fields marked `# optional` may be omitted when not applicable.

```yaml
metadata:
  skill: <skill-name>             # e.g., ospf_adjacency, bgp_peering
  protocol: <protocol>            # e.g., ospf, bgp, eigrp
  generated: <ISO-8601 timestamp>
  intent_source: data/INTENT.json
  scope: <all | device-filtered>  # "all" or comma-separated device names if $ARGUMENTS was passed
  pair_count: <N>                 # number of device pairs (or targets for single-device skills)
  test_count: <N>                 # total number of test entries

tests:
  - id: <skill>_<criterion>_<deviceA>_<deviceB>   # unique, stable, sortable
    criterion: <criterion_id>     # skill-specific: ADJ-01, BGP-01, etc.
    rfc: "<RFC reference>"        # e.g., "RFC 2328 §10.3" — mandatory
    description: "<human-readable one-liner>"
    device:
      name: <deviceA>
      host: <ip-address>          # from inventory, used by renderers to connect
      platform: <platform>        # cisco_iosxe, arista_eos, juniper_junos, aruba_aoscx, mikrotik_routeros, vyos
      cli_style: <cli_style>      # ios, eos, junos, aos, routeros, vyos
      interface: <interface>      # optional — local interface for this link
      ip: <ip>                    # optional — local IP on this link
    peer:                         # optional — present for adjacency/peering tests
      name: <deviceB>
      host: <ip-address>
      platform: <platform>
      cli_style: <cli_style>
      rid: <router-id>            # optional — used for neighbor matching
      interface: <interface>      # optional
      ip: <ip>                    # optional
    context:                      # skill-specific topology fields
      # OSPF adjacency fields:
      area: <area_id>             # e.g., 0, 1
      area_type: <type>           # normal, stub, nssa
      # BGP peering fields (future):
      # asn: <asn>
      # peer_asn: <peer_asn>
      # ...extensible per skill
    query:
      ssh_cli: "<vendor-specific show command>"
    assertion:
      type: <assertion_type>      # interface_up | neighbor_presence | neighbor_state | timer_match | area_match | stub_agreement | mtu_match | router_id_unique
      field: <what to check>      # e.g., "neighbor_state", "hello_interval", "area_id"
      expected: <expected_value>  # specific value — never null or "any"
      match_by:                   # optional — omit for process-level checks (e.g., router_id_unique)
        router_id: <rid>          # for neighbor table lookups
        interface: <iface>        # for interface-specific checks
        # ...one or both of the above
```

### ID Naming Convention

Test IDs must be: `<skill>_<criterion>_<deviceA>_<deviceB>` where deviceA < deviceB alphabetically.

For per-device criteria (e.g., ADJ-08 Router ID Unique): `<skill>_<criterion>_<device>`.

Examples:
- `ospf_adj_ADJ-02_A1M_D1C`
- `ospf_adj_ADJ-03_C1J_D1C`
- `ospf_adj_ADJ-08_D1C`

---

## Pytest Renderer Guidance

Generate the following files under `output/pytest/`:

### `conftest.py`
- Device connection fixtures using `scrapli` (SSH)
- Look up device data from `data/INTENT.json` under the `routers` key — the JSON structure is `{"autonomous_systems": {...}, "routers": {"A1M": {...}, "D2B": {...}, ...}}`. Device fields (`host`, `cli_style`, etc.) are directly on each router object, not nested under an `intent` sub-key.
- `cli_style` maps to scrapli platform (see table below)
- Fixture scope: `session` for connection reuse

### `test_<skill>.py`
- One test file, or split by criterion category if test count > 100
- Parametrized tests from the spec entries — iterate `tests` list in the YAML
- Each test function:
  - Takes `device_conn` fixture (scrapli connection)
  - Sends `query.ssh_cli` via `conn.send_command()`
  - Applies `assertion` logic to the output (text parsing)
  - Uses `match_by` to identify the correct row/entry before asserting
  - Docstring includes `criterion`, `rfc`, and `description`
- **No ghost assertions**: assert `assertion.field == assertion.expected`, not `assert result`
- Run with `pytest --junitxml=output/pytest/results.xml`

### Platform → Scrapli mapping

| cli_style | scrapli platform |
|-----------|-----------------|
| ios | `cisco_iosxe` |
| eos | `arista_eos` |
| junos | `juniper_junos` |
| aos | `aruba_aoscx` |
| routeros | `mikrotik_routeros` |
| vyos | `linux` |

---

## Ansible Renderer Guidance

Generate the following files under `output/ansible/`:

### `inventory.yml`
- Derived from INTENT.json device data
- Group devices by `location` or `cli_style`
- `ansible_host` = `host` field; `ansible_network_os` = platform

### `playbook_<skill>.yml`
- One playbook, one play per device (or per criterion category)
- Use `cisco.ios.ios_command`, `arista.eos.eos_command`, `junipernetworks.junos.junos_command`, etc. per platform
  — or use the generic `ansible.netcommon.cli_command` module with `network_cli` connection
- For each test entry:
  - Task name includes `criterion`, `description`
  - `cli_command` sends `query.ssh_cli`
  - `assert` task validates `assertion.expected` appears in output with correct `match_by` context
  - Include `vars.rfc` annotation for traceability
- **No ghost assertions**: use `assert` with a specific expected value or regex that is equivalent
- Configure JUnit output: `ANSIBLE_JUNIT_OUTPUT_DIR=output/ansible/` with `junit` callback

### Inventory mapping

`ansible_network_os` per `cli_style`:

| cli_style | ansible_network_os |
|-----------|--------------------|
| ios | cisco.ios.ios |
| eos | arista.eos.eos |
| junos | junipernetworks.junos.junos |
| aos | arubanetworks.aoscx.aoscx |
| routeros | community.routeros.routeros |
| vyos | vyos.vyos.vyos |
