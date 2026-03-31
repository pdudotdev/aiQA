# Renderer Guidance — Pytest and Ansible

Read this before rendering the YAML spec into pytest or Ansible artifacts.
The YAML spec schema is in `.claude/spec-schema.md`.

---

## Pytest Renderer

Generate under `output/pytest/`:

### `conftest.py`
- Device connection fixtures using `scrapli` (SSH)
- Load device data from `data/INTENT.json` — structure: `{"routers": {"A1M": {...}, ...}}`. Fields (`host`, `cli_style`) are directly on each router object.
- Fixture scope: `session` for connection reuse
- Session-level rollback registry (see below)

### `test_<skill>.py`
- Parametrized from YAML spec — iterate `tests` list
- Docstring: include `criterion`, `rfc`, `description`
- **No ghost assertions** — never `assert result` or `assert len(x) > 0`
- Run: `pytest --junitxml=output/pytest/results.xml`

### Test pattern — `try/finally`

Every test follows this pattern:

```python
def test_active(device_conn, peer_conn, test_entry):
    setup = test_entry["setup"]
    teardown = test_entry["teardown"]

    # Pre-flight: verify baseline (show command → send_command)
    out = device_conn.send_command(setup["snapshot_cli"]).result
    baseline = parse_field(out, setup["snapshot_field"])
    assert baseline == setup["snapshot_expected"], f"Pre-flight failed: {baseline!r} != {setup['snapshot_expected']!r}"

    register_rollback(device_conn, teardown["ssh_cli"])
    try:
        # Setup: config command → send_configs (enters config mode automatically)
        device_conn.send_configs(setup["ssh_cli"].split("\n"))
        # wait
        if test_entry["wait"]["type"] in ("convergence", "fixed"):
            time.sleep(test_entry["wait"]["seconds"])
        elif test_entry["wait"]["type"] == "poll":
            _poll_until(device_conn, test_entry["wait"])
        # assert (show command → send_command)
        result = peer_conn.send_command(test_entry["query"]["ssh_cli"]).result
        actual = parse_and_match(result, test_entry["assertion"], test_entry.get("match_by"))
        assert actual == test_entry["assertion"]["expected"]
    finally:
        # Teardown: config command → send_configs
        device_conn.send_configs(teardown["ssh_cli"].split("\n"))
        # Verify rollback (show command → send_command)
        verify = device_conn.send_command(teardown["verify_cli"]).result
        restored = parse_field(verify, teardown["verify_field"])
        assert restored == teardown["verify_expected"], f"ROLLBACK FAILED: {restored!r}"
        deregister_rollback(device_conn, teardown["ssh_cli"])
```

**Important:** Use `send_configs()` (config mode) for `setup.ssh_cli` and `teardown.ssh_cli`. Use `send_command()` (operational mode) for show commands (`snapshot_cli`, `query.ssh_cli`, `verify_cli`). scrapli's `send_configs()` automatically enters and exits config mode on platforms that require it (IOS, EOS, JunOS, AOS-CX). RouterOS commands work with either method since RouterOS has no separate config mode.

### Session rollback registry (conftest.py)

```python
_rollback_registry = []

def register_rollback(conn, cmd): _rollback_registry.append((conn, cmd))
def deregister_rollback(conn, cmd): _rollback_registry.remove((conn, cmd))

@pytest.fixture(scope="session", autouse=True)
def emergency_rollback():
    yield
    for conn, cmd in _rollback_registry:
        try: conn.send_configs(cmd.split("\n"))
        except Exception as e: print(f"[EMERGENCY ROLLBACK] {cmd}: {e}")
```

### Poll-until helper (conftest.py)

```python
def _poll_until(conn, wait_spec):
    """Poll a show command until condition is met or timeout expires."""
    import time
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
```

### Connection scoping

The `connections` fixture MUST only connect to devices referenced in the YAML spec — not all devices in INTENT.json. Extract unique device names from the spec's `tests[].device.name` and `tests[].peer.name` fields, then connect only to those. This prevents test failures when unused devices are unreachable.

### Platform → Scrapli mapping

| cli_style | scrapli platform |
|-----------|-----------------|
| ios | `cisco_iosxe` |
| eos | `arista_eos` |
| junos | `juniper_junos` |
| aos | `aruba_aoscx` |
| routeros | `mikrotik_routeros` |
| vyos | `linux` | *Not a built-in scrapli platform — requires `scrapli_community` or a custom platform definition* |

---

## Ansible Renderer

Generate under `output/ansible/`:

### `inventory.yml`
- Derived from INTENT.json. Group by `location` or `cli_style`.
- `ansible_host` = `host`; `ansible_network_os` = see mapping below.

### `playbook_<skill>.yml`
- One play per device or criterion category
- Use `ansible.netcommon.cli_command` with `network_cli`, or platform-specific modules
- Per test entry: task name = `[<criterion>] <description>`, send `query.ssh_cli`, assert `assertion.expected`
- Include `vars.rfc` per task
- **No ghost assertions**
- JUnit output: `ANSIBLE_JUNIT_OUTPUT_DIR=output/ansible/` with `junit` callback

### Test pattern — `block/always`

Every test MUST use `block/always` — never `post_tasks`, `handlers`, or `rescue`. `post_tasks` does NOT run if a task in `tasks` fails, which means teardown is skipped and the device is left misconfigured. `block/always` guarantees teardown runs regardless of test outcome — this is the Ansible equivalent of pytest's `try/finally`.

Every test follows this pattern:

```yaml
- name: "[CRITERION] description"
  vars: { rfc: "RFC X §Y" }
  block:
    - name: "Pre-flight"
      ansible.netcommon.cli_command: { command: "{{ setup.snapshot_cli }}" }
      register: baseline
    - ansible.builtin.assert:
        that: "'{{ setup.snapshot_expected }}' in baseline.stdout"
        fail_msg: "Pre-flight failed"
    - name: "Setup"
      ansible.netcommon.cli_command: { command: "{{ setup.ssh_cli }}" }
    - ansible.builtin.pause: { seconds: "{{ wait.seconds }}" }
    - name: "Verify"
      ansible.netcommon.cli_command: { command: "{{ query.ssh_cli }}" }
      register: result
    - ansible.builtin.assert:
        that: "'{{ assertion.expected }}' in result.stdout"
        fail_msg: "[{{ criterion }}] Expected {{ assertion.expected }}"
  always:
    - ansible.netcommon.cli_command: { command: "{{ teardown.ssh_cli }}" }
    - ansible.netcommon.cli_command: { command: "{{ teardown.verify_cli }}" }
      register: rollback_check
    - ansible.builtin.assert:
        that: "'{{ teardown.verify_expected }}' in rollback_check.stdout"
        fail_msg: "ROLLBACK FAILED"
```

### Emergency rollback playbook

Always generate `playbook_<skill>_rollback.yml` alongside the main playbook. This runs all teardown commands unconditionally — use it to recover from interrupted test runs.

### Ansible network_os mapping

| cli_style | ansible_network_os |
|-----------|--------------------|
| ios | cisco.ios.ios |
| eos | arista.eos.eos |
| junos | junipernetworks.junos.junos |
| aos | arubanetworks.aoscx.aoscx |
| routeros | community.routeros.routeros |
| vyos | vyos.vyos.vyos |
