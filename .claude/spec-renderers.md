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

    # Pre-flight: verify baseline
    out = device_conn.send_command(setup["snapshot_cli"]).result
    baseline = parse_field(out, setup["snapshot_field"])
    assert baseline == setup["snapshot_expected"], f"Pre-flight failed: {baseline!r} != {setup['snapshot_expected']!r}"

    register_rollback(device_conn, teardown["ssh_cli"])
    try:
        device_conn.send_command(setup["ssh_cli"])
        # wait
        if test_entry["wait"]["type"] in ("convergence", "fixed"):
            time.sleep(test_entry["wait"]["seconds"])
        elif test_entry["wait"]["type"] == "poll":
            _poll_until(device_conn, test_entry["wait"])
        # assert
        result = peer_conn.send_command(test_entry["query"]["ssh_cli"]).result
        actual = parse_and_match(result, test_entry["assertion"], test_entry.get("match_by"))
        assert actual == test_entry["assertion"]["expected"]
    finally:
        device_conn.send_command(teardown["ssh_cli"])
        verify = device_conn.send_command(teardown["verify_cli"]).result
        restored = parse_field(verify, teardown["verify_field"])
        assert restored == teardown["verify_expected"], f"ROLLBACK FAILED: {restored!r}"
        deregister_rollback(device_conn, teardown["ssh_cli"])
```

### Session rollback registry (conftest.py)

```python
_rollback_registry = []

def register_rollback(conn, cmd): _rollback_registry.append((conn, cmd))
def deregister_rollback(conn, cmd): _rollback_registry.remove((conn, cmd))

@pytest.fixture(scope="session", autouse=True)
def emergency_rollback():
    yield
    for conn, cmd in _rollback_registry:
        try: conn.send_command(cmd)
        except Exception as e: print(f"[EMERGENCY ROLLBACK] {cmd}: {e}")
```

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
