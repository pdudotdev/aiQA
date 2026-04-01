# Renderer Guidance — Pytest and Ansible

Read this before rendering the YAML spec into pytest or Ansible artifacts.
The YAML spec schema is in `.claude/spec-schema.md`.

---

## Pytest Renderer

Generate under `output/pytest/`. Uses **Netmiko** for SSH connections.

### `conftest.py`
- Device connection fixtures using `netmiko.ConnectHandler` (SSH)
- Fixture scope: `session` for connection reuse
- Session-level rollback registry (see below)
- MUST load all YAML specs via `spec_dir.glob("*.yaml")` — never hardcode a specific filename
- Shared across test files — do not duplicate if it already exists

### `test_<skill>.py`
- Parametrized from YAML spec — load the `tests` list and parametrize directly from it (never hardcode indices like `[0, 1, 2, 3]`)
- Docstring: include `criterion`, `rfc`, `description`
- **No ghost assertions** — never `assert result` or `assert len(x) > 0`
- Run: `pytest output/pytest/` (JUnit XML auto-generated at `output/pytest/results.xml` via `conftest.py` hook)

### Test pattern — `try/finally`

Every test follows this pattern:

```python
def test_active(connections, test_entry):
    setup = test_entry["setup"]
    teardown = test_entry["teardown"]
    wait = test_entry["wait"]
    cli_style = test_entry["device"]["cli_style"]

    device_conn = connections[test_entry["device"]["name"]]
    peer_conn = connections[test_entry["peer"]["name"]]

    # Pre-flight: verify baseline (show command → send_command)
    out = device_conn.send_command(setup["snapshot_cli"])
    baseline = parse_field(out, setup["snapshot_field"])
    assert baseline == setup["snapshot_expected"], f"Pre-flight failed: {baseline!r} != {setup['snapshot_expected']!r}"

    register_rollback(device_conn, teardown["ssh_cli"])
    try:
        # Setup: config command → send_config_set (handles config mode per platform)
        device_conn.send_config_set(setup["ssh_cli"].split("\n"))
        if cli_style in COMMIT_PLATFORMS:
            device_conn.commit()
        # wait
        if wait["type"] in ("convergence", "fixed"):
            time.sleep(wait["seconds"])
        elif wait["type"] == "poll":
            _poll_until(peer_conn, wait)
        # assert (show command → send_command)
        result = peer_conn.send_command(test_entry["query"]["ssh_cli"])
        actual = parse_and_match(result, test_entry["assertion"], test_entry["assertion"].get("match_by"))
        assert actual == test_entry["assertion"]["expected"]
    finally:
        # Teardown: config command → send_config_set
        device_conn.send_config_set(teardown["ssh_cli"].split("\n"))
        if cli_style in COMMIT_PLATFORMS:
            device_conn.commit()
        # Wait for reconvergence
        time.sleep(wait["seconds"])
        # Verify rollback — re-check the same field that was changed (setup.snapshot_*)
        verify = device_conn.send_command(setup["snapshot_cli"])
        restored = parse_field(verify, setup["snapshot_field"])
        assert restored == setup["snapshot_expected"], f"ROLLBACK FAILED: {restored!r}"
        deregister_rollback(device_conn, teardown["ssh_cli"])
```

**Important:** Use `send_config_set()` for `setup.ssh_cli` and `teardown.ssh_cli`. Use `send_command()` for show commands (`snapshot_cli`, `query.ssh_cli`). Netmiko's `send_config_set()` automatically enters and exits config mode on platforms that require it (IOS, EOS, JunOS, AOS-CX). For RouterOS (no config mode), Netmiko's `NoConfig` mixin sends commands directly — no special handling needed. For JunOS and VyOS, call `conn.commit()` after `send_config_set` to apply candidate config. Netmiko's `send_command()` returns a string directly (no `.result` accessor).

### Session rollback registry (conftest.py)

```python
_rollback_registry = []

def register_rollback(conn, cmd): _rollback_registry.append((conn, cmd))
def deregister_rollback(conn, cmd):
    try: _rollback_registry.remove((conn, cmd))
    except ValueError: pass

@pytest.fixture(scope="session", autouse=True)
def emergency_rollback():
    yield
    for conn, cmd in _rollback_registry:
        try: conn.send_config_set(cmd.split("\n"))
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
        out = conn.send_command(cli)
        if condition in out:
            return
        time.sleep(interval)
    raise TimeoutError(f"Poll condition {condition!r} not met after {timeout}s")
```

### JUnit XML auto-configuration (conftest.py)

```python
def pytest_configure(config):
    """Auto-enable JUnit XML output if not specified on command line."""
    if not config.option.xmlpath:
        config.option.xmlpath = str(Path(__file__).parent / "results.xml")
```

Generates `output/pytest/results.xml` next to the test files regardless of CWD. If the user passes `--junitxml=custom.xml`, their path takes precedence.

### Connection scoping

The `connections` fixture MUST only connect to devices referenced in the YAML spec — not all devices in INTENT.json. Load all specs via `spec_dir.glob("*.yaml")`, extract unique device names from `tests[].device.name` and `tests[].peer.name`, then connect only to those. This prevents test failures when unused devices are unreachable. Use `conn.disconnect()` for cleanup.

### Platform → Netmiko mapping

| cli_style | Netmiko device_type | Config mode | Commit required? |
|-----------|-------------------|-------------|-----------------|
| ios | `cisco_ios` | `configure terminal` | No |
| eos | `arista_eos` | `configure terminal` | No |
| junos | `juniper_junos` | `configure` | **Yes** — `conn.commit()` |
| aos | `aruba_aoscx` | `configure` | No |
| routeros | `mikrotik_routeros` | None (`NoConfig`) | No |
| vyos | `vyos` | `configure` | **Yes** — `conn.commit()` + `conn.exit_config_mode()` |

```python
PLATFORM_MAP = {
    "ios": "cisco_ios",
    "eos": "arista_eos",
    "junos": "juniper_junos",
    "aos": "aruba_aoscx",
    "routeros": "mikrotik_routeros",
    "vyos": "vyos",
}
COMMIT_PLATFORMS = {"junos", "vyos"}
```

---

## Ansible Renderer

Generate under `output/ansible/`:

### `inventory.yml`
- Derived from INTENT.json. Group by `location` or `cli_style`.
- `ansible_host` = `host`; `ansible_network_os` = see mapping below.
- Credentials via env var with fallback as group vars under `all.vars`: `ansible_user: "{{ lookup('env', 'NETWORK_USER') | default('admin', true) }}"` and `ansible_password: "{{ lookup('env', 'NETWORK_PASSWORD') | default('admin', true) }}"`.

### `playbook_<skill>.yml`
- One play per device or criterion category
- Use `ansible.netcommon.cli_command` for show/exec commands, `ansible.netcommon.cli_config` for config commands
- Per test entry: task name = `[<criterion>] <description>`, send `query.ssh_cli`, assert `assertion.expected`
- Include `vars.rfc` per task
- **No ghost assertions**
- JUnit output: auto-configured via `ansible.cfg` (`junit` callback enabled, results written to `output/ansible/`)

### Test pattern — `block/always`

Every test MUST use `block/always` — never `post_tasks`, `handlers`, or `rescue`. `post_tasks` does NOT run if a task in `tasks` fails, which means teardown is skipped and the device is left misconfigured. `block/always` guarantees teardown runs regardless of test outcome — this is the Ansible equivalent of pytest's `try/finally`.

**Important:** Use `ansible.netcommon.cli_config` for config commands (`setup.ssh_cli`, `teardown.ssh_cli`). Use `ansible.netcommon.cli_command` for show/exec commands (`setup.snapshot_cli`, `query.ssh_cli`, `teardown.verify_cli`). `cli_config` automatically enters and exits config mode on platforms that require it (IOS, EOS, JunOS, AOS-CX). RouterOS has no separate config mode, but `cli_config` still works — use it uniformly for all config commands regardless of platform.

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
      ansible.netcommon.cli_config:
        config: "{{ setup.ssh_cli }}"
    - ansible.builtin.pause: { seconds: "{{ wait.seconds }}" }
    - name: "Verify"
      ansible.netcommon.cli_command: { command: "{{ query.ssh_cli }}" }
      register: result
    - ansible.builtin.assert:
        that: "'{{ assertion.expected }}' in result.stdout"
        fail_msg: "[{{ criterion }}] Expected {{ assertion.expected }}"
  always:
    - name: "Teardown"
      ansible.netcommon.cli_config:
        config: "{{ teardown.ssh_cli }}"
    - ansible.builtin.pause: { seconds: "{{ wait.seconds }}" }
    - name: "Verify rollback"
      ansible.netcommon.cli_command: { command: "{{ teardown.verify_cli }}" }
      register: rollback_check
    - ansible.builtin.assert:
        that: "'{{ teardown.verify_expected }}' in rollback_check.stdout"
        fail_msg: "ROLLBACK FAILED"
```

**Cross-device tests:** When `setup.target` differs from the play's `hosts`, use `delegate_to: {{ setup.target }}` on the Setup and Teardown tasks. Pre-flight, Verify, and Rollback verification run on the play host (the verification device).

### Emergency rollback playbook

Always generate `playbook_<skill>_rollback.yml` alongside the main playbook. This runs all teardown commands unconditionally — use it to recover from interrupted test runs. Rollback tasks use `ansible.netcommon.cli_config` (they send config commands to revert changes). Every task in the rollback playbook MUST have `ignore_errors: true` so that one failed rollback does not prevent subsequent rollbacks from running.

### `ansible.cfg`

Generate `output/ansible/ansible.cfg` (shared — do not duplicate if it already exists):

```ini
[defaults]
callbacks_enabled = junit

[callback_junit]
output_dir = ./
```

Auto-enables JUnit XML results when `ansible-playbook` is run from `output/ansible/` or with `ANSIBLE_CONFIG=output/ansible/ansible.cfg`.

### Ansible network_os mapping

| cli_style | ansible_network_os |
|-----------|--------------------|
| ios | cisco.ios.ios |
| eos | arista.eos.eos |
| junos | junipernetworks.junos.junos |
| aos | arubanetworks.aoscx.aoscx |
| routeros | community.routeros.routeros |
| vyos | vyos.vyos.vyos |
