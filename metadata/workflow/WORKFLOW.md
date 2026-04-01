# aiQA — How It Works

aiQA is a framework that gives Claude the context it needs to generate professional, RFC-compliant network test cases from design intent. It produces framework-agnostic YAML test specifications and renders them into executable pytest suites and Ansible playbooks.

---

## The Tools

aiQA exposes 3 tools registered in `server.py`:

| Tool | Purpose | Backend |
|------|---------|---------|
| `search_knowledge_base` | Semantic search over RFCs and vendor docs | ChromaDB + MiniLM embeddings |
| `query_intent` | Network design intent (roles, OSPF areas, links, router IDs, baselines) | `data/INTENT.json` |
| `list_devices` | Inventory summary filtered by CLI style | `data/INTENT.json` |

### The Knowledge Base

`search_knowledge_base` performs RAG (Retrieval-Augmented Generation):

1. **Ingestion** (one-time, via `make ingest` → `ingest.py --clean`): Markdown files from `docs/` are chunked, embedded with `all-MiniLM-L6-v2`, and stored in ChromaDB with metadata (`vendor`, `topic`, `source`, `protocol`). Each chunk gets a contextual header prepended (`[Source: filename | Protocol: protocol]`) for better embedding quality. Metadata is derived from filenames by `ingest.py:extract_metadata()`.
2. **Query**: The search query is embedded into the same vector space. ChromaDB returns the top-k most similar chunks by cosine distance.
3. **Filters**: Optional `vendor`, `topic`, and `protocol` filters narrow results before similarity search. Compound filtering is supported (e.g., `vendor=cisco_ios` + `protocol=ospf`).

The KB contains:
- Verification commands (show commands per vendor)
- Configuration commands (for setup blocks)
- Rollback/revert patterns (for teardown blocks) — each vendor doc has a "Configuration Revert Patterns" section
- RFC sections and protocol-specific gotchas

Device inventory and design intent are NOT in ChromaDB — they are served at query time by `list_devices` and `query_intent`.

See [OPTIMIZATIONS.md](../scalability/OPTIMIZATIONS.md) for the full RAG optimization roadmap.

---

## Test Model

All tests are active: configure a condition → wait → check the result → teardown (revert). There are no read-only tests.

Each test entry has three mandatory blocks:

```
setup  →  wait  →  assert  →  teardown (always runs)
```

| Block | Purpose | Fields |
|-------|---------|--------|
| `setup` | Configure the test condition on the target device; snapshot the baseline value | `target`, `ssh_cli`, `snapshot_cli`, `snapshot_field`, `snapshot_expected` |
| `wait` | Allow protocol convergence after the config change | `type` (convergence/fixed/poll), `seconds` |
| `teardown` | Revert the config change; verify rollback succeeded | `ssh_cli`, `verify_cli`, `verify_field`, `verify_expected` |

`teardown.verify_expected` must equal `setup.snapshot_expected`. Both values come from `INTENT.json` — never guessed.

---

## The General QA Skill (`/qa`)

The `/qa` skill is the only skill in aiQA. It handles any protocol, any feature, any test type via natural language requests. No per-protocol skill files are needed.

### 13-Step Workflow (Steps 0–12)

```
Step 0  — Preflight         list_devices() + search_knowledge_base() — verify MCP server responds
Step 1  — Parse Request     Extract protocol, feature, device scope, failure mode from $ARGUMENTS
Step 2  — Resolve Devices   query_intent("<device>") per device + list_devices() — scope from INTENT.json
Step 3  — Clarify           Ask user if genuinely ambiguous (one round only)
Step 4  — Research          search_knowledge_base() — vendor show/config/rollback commands + RFC grounding
Step 5  — Derive Criteria   Apply QC-1 through QC-8 to build test criteria from intent + KB results
Step 6  — Present Test Plan Mandatory pause — user confirms before any files are generated
Step 7  — Load spec-schema  Read .claude/spec-schema.md (YAML field definitions + schema rules)
Step 8  — Generate YAML     Write output/spec/<protocol>_<feature>[_scope].yaml
Step 9  — Load spec-renderers  Read .claude/spec-renderers.md (pytest + Ansible rendering patterns)
Step 10 — Render Pytest     Write output/pytest/test_<...>.py + conftest.py (Netmiko SSH, try/finally)
Step 11 — Render Ansible    Write output/ansible/playbook_<...>.yml + inventory.yml (block/always)
Step 12 — Summary           Final table of outputs and test counts
```

### Scoped Intent Queries (Step 2)

- Explicit device names in the request → `query_intent("<device>")` per device (one call each)
- Role-based or "all" scope → `query_intent()` with no argument (full topology)

This keeps input token consumption proportional to the scope of the request.

### Step 6: Test Plan Confirmation

The agent never generates files without user confirmation. The plan always includes a ⚠️ warning that tests will modify device configuration.

```
⚠️  These tests WILL modify device configuration. Rollback is automatic but is NOT
    guaranteed if the connection drops mid-test. Do not run against production
    devices without explicit approval.

| # | Criterion | Setup (target) | Verify (target) | Expected outcome |
|---|-----------|----------------|-----------------|------------------|
| 1 | TMISMATCH-01 | C2A: set hello=15 | DC1A: check state | state != FULL |
...

Proceed?
```

If the request describes only verification of current state without specifying a condition to test, the agent asks the user to be more specific.

---

## Test Generation Examples

### Example 1: `/qa OSPF timer mismatch tests between C1J and D1C`

```
Step 0  — Preflight: all 3 tools responding

Step 1  — Parse:
  protocol=ospf, feature=timer mismatch, devices={C1J, D1C}

Step 2  — Resolve:
  query_intent("C1J")  → junos, Area 0, hello=10, dead=40, RID=22.22.22.11
  query_intent("D1C")  → ios, Area 0, hello=10, dead=40, RID=11.11.11.11
  list_devices()       → cli_style, host for both

Step 3  — No ambiguity → skip

Step 4  — Research:
  search_knowledge_base(vendor=juniper_junos, protocol=ospf)   → JunOS timer show + config/revert
  search_knowledge_base(vendor=cisco_ios, protocol=ospf)       → IOS timer show + config/revert
  search_knowledge_base(topic=rfc, protocol=ospf, query="hello dead timer adjacency")

Step 5  — Criteria:
  C1J (junos) ≠ D1C (ios) → cross-vendor → QC-8: both directions
    TMISMATCH-01: set hello=15 on C1J → verify D1C neighbor not FULL → rollback
    TMISMATCH-02: set dead=80 on C1J → verify D1C neighbor not FULL → rollback
    TMISMATCH-03: set hello=15 on D1C → verify C1J neighbor not FULL → rollback
    TMISMATCH-04: set dead=80 on D1C → verify C1J neighbor not FULL → rollback

Step 6  — Present plan:
  ⚠️  4 tests, all modify configuration
  "Proceed?"
  → User confirms

Step 7  — Load .claude/spec-schema.md

Step 8  — Generate YAML spec
  → 4 tests
  → write output/spec/ospf_timer_C1J_D1C.yaml

Step 9  — Load .claude/spec-renderers.md

Step 10 — Render Pytest
  → try/finally for all tests, rollback registry in conftest.py
  → write output/pytest/test_ospf_timer_C1J_D1C.py
  → write output/pytest/conftest.py

Step 11 — Render Ansible
  → block/always for all tests
  → write output/ansible/playbook_ospf_timer_C1J_D1C.yml
  → write output/ansible/playbook_ospf_timer_C1J_D1C_rollback.yml
  → write output/ansible/inventory.yml

Step 12 — Summary: 4 tests
```

### Example 2: `/qa OSPF hello-interval mismatch test between A2A and A3A`

```
Step 1  — protocol=ospf, feature=hello mismatch, devices={A2A, A3A}
Step 2  — A2A: eos, Area 1 stub | A3A: eos, Area 1 stub
Step 4  — KB: arista_eos timer config + revert commands, RFC 2328 §10.5
Step 5  — A2A (eos) = A3A (eos) → same-vendor → QC-8: ONE direction only
          TMISMATCH-01: set hello=15 on A2A → verify A3A neighbor not FULL → rollback
          TMISMATCH-02: set dead=80 on A2A → verify A3A neighbor not FULL → rollback
          (no mirror — same teardown syntax, zero additional coverage)
Step 6  — Present plan: ⚠️  2 tests, "Proceed?"
Step 8  — Generate spec: 2 tests
Step 10 — Pytest: try/finally × 2
Step 11 — Ansible: block/always × 2 + rollback playbook
```

---

## Output Pipeline

The YAML spec is the canonical source of truth — renderers are mechanical transforms, not independent test logic.

```
data/INTENT.json
      │
      ▼
  YAML Spec                    ← canonical, framework-agnostic
  output/spec/
      │
      ├──► Pytest Suite         ← Netmiko SSH, try/finally for all tests
      │    output/pytest/
      │
      └──► Ansible Playbook     ← cli_command module, block/always for all tests
           output/ansible/        + emergency rollback playbook
```

### YAML Spec Fields

Every test entry contains:

| Field | Description |
|-------|-------------|
| `id` | Stable, sortable test identifier (`<protocol>_<feature>_<criterion>_<deviceA>_<deviceB>`) |
| `criterion` | Agent-derived criterion ID (e.g., `TMISMATCH-01`, `ADJ-03`) |
| `rfc` | Mandatory specific RFC section citation |
| `description` | Human-readable one-liner |
| `device` + `peer` | Full inventory fields (host, platform, cli_style, interface) |
| `query.ssh_cli` | Exact vendor-specific show command (the check step) |
| `assertion` | Type, field, expected value, match_by — no ghost assertions |
| `context` | Topology fields (area, area_type, etc.) |
| `setup` | Target device, config command, pre-flight snapshot |
| `wait` | Post-config convergence delay |
| `teardown` | Rollback command, verify rollback succeeded |

### Pytest Renderer

- Uses `Netmiko` for SSH connections (cli_style mapped to Netmiko platform)
- `conftest.py` provides session-scoped connection fixtures parametrized by device
- All tests: `try/finally` — pre-flight snapshot, configure, wait, assert, teardown always runs
- Session-level rollback registry in `conftest.py` for interrupted suites
- JUnit XML auto-configured via `conftest.py` `pytest_configure` hook — `output/pytest/results.xml`
- Run: `pytest output/pytest/`

### Ansible Renderer

- Uses `ansible.netcommon.cli_command` (generic) or platform-specific modules
- All tests: `block/always` — teardown in `always` block
- Emergency rollback playbook generated alongside every playbook
- JUnit XML auto-configured via generated `ansible.cfg` (`junit` callback enabled)
- Task names include criterion ID and description for traceability
- `vars.rfc` annotation per task for audit trail

---

## Quality Controls (QC-1 through QC-8)

| Rule | Description |
|------|-------------|
| QC-1 | Every test cites a specific RFC section |
| QC-2 | Bidirectional tests (adjacency, peering) generate one entry per direction |
| QC-3 | `query.ssh_cli` uses the correct vendor command; one device, one executable CLI per entry |
| QC-4 | `assertion.expected` is a specific value — never null, "any", or "not empty" |
| QC-5 | `assertion.match_by.router_id` comes from intent data |
| QC-6 | Test IDs follow `<protocol>_<feature>_<criterion>_<setupDevice>_<verifyDevice>` (setup target first, verify target second) |
| QC-7 | Every entry has `setup` + `wait` + `teardown`; teardown verify re-checks same parameter: `verify_cli` = `snapshot_cli`, `verify_field` = `snapshot_field`, `verify_expected` = `snapshot_expected` |
| QC-8 | Cross-vendor pairs: tests in BOTH directions; same-vendor pairs: ONE direction ONLY |

---

## Customization

| What | Where | How |
|------|-------|-----|
| Network intent + inventory | `data/INTENT.json` | Edit directly; one JSON object per router |
| Protocol docs | `docs/*.md` | Add Markdown files; run `make ingest` to rebuild ChromaDB |
| Rollback/revert patterns | `docs/vendor_*.md` | Each vendor doc has a "Configuration Revert Patterns" section |
| Skill workflow | `.claude/skills/qa/SKILL.md` | Edit the general QA skill to adjust methodology |
| YAML spec schema | `.claude/spec-schema.md` | Field definitions and schema rules |
| Renderer patterns | `.claude/spec-renderers.md` | pytest and Ansible rendering guidance |
