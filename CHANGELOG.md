# Changelog

## v1.3 — 2026-04-01

### Pytest Renderer — Migrated from scrapli to Netmiko

- Replaced scrapli with Netmiko for all pytest SSH connections — fixes `AttributeError` on RouterOS and VyOS (scrapli's `GenericDriver` does not have `send_configs`)
- `send_configs()` → `send_config_set()` — Netmiko's `NoConfig` mixin makes this work uniformly across all platforms, including RouterOS (no config mode)
- Added `COMMIT_PLATFORMS` set (`junos`, `vyos`) — JunOS and VyOS require explicit `conn.commit()` after config changes to apply candidate config
- Platform mapping updated to Netmiko device_type strings: `cisco_ios`, `arista_eos`, `juniper_junos`, `aruba_aoscx`, `mikrotik_routeros`, `vyos`
- `conn.send_command(cmd).result` → `conn.send_command(cmd)` — Netmiko returns string directly
- `conn.close()` → `conn.disconnect()`

### Spec Schema and Quality Controls

- **ID naming convention**: fixed contradiction — direction-encoded (`<setupDevice>_<verifyDevice>`), not alphabetical. Updated in spec-schema.md, SKILL.md QC-6, WORKFLOW.md
- **device/peer semantics**: `device` = setup target, `peer` = verify target — now explicit in schema comments
- **peer.rid**: clarified as the peer device's own router_id from INTENT.json
- **QC-7 strengthened**: teardown verify_cli/verify_field/verify_expected MUST equal setup snapshot_cli/snapshot_field/snapshot_expected — ensures rollback verification checks the same parameter that was changed
- **CLAUDE.md bidirectional rule**: added same-vendor exception to match QC-8 (same `cli_style` pairs → one direction only)
- **Scope guard**: SKILL.md Step 1 warns for broad multi-protocol/multi-device requests

### Renderer Improvements

- conftest.py MUST use `spec_dir.glob("*.yaml")` — never hardcode spec filenames (shareability fix)
- Parametrization MUST use loaded spec list — never hardcode indices
- Emergency rollback playbook: all tasks MUST have `ignore_errors: true` (best-effort recovery)
- `deregister_rollback` catches `ValueError` on mismatch (robustness fix)
- spec-renderers.md template: fixed `match_by` access from `test_entry.get("match_by")` to `test_entry["assertion"].get("match_by")`

### Documentation

- WORKFLOW.md: all scrapli references updated to Netmiko; QC-6 and QC-7 updated; C1J RID corrected (10.10.10.10 → 22.22.22.11)

---

## v1.2 — 2026-03-31

### All Tests Are Active — Tier Distinction Removed

- Removed the Tier 1 (read-only) / Tier 2 (active) distinction — all tests now follow configure-wait-check-teardown
- `tier` field removed from YAML spec metadata and per-entry schema
- `rollback_risk` field removed (no behavioral effect; `description` field is sufficient)
- `setup`, `wait`, `teardown` blocks are now mandatory for every test entry
- `try/finally` (pytest) and `block/always` (Ansible) are the only rendering patterns
- Emergency rollback playbook always generated alongside every Ansible playbook
- Session rollback registry always present in `conftest.py`
- Step 1 tier detection logic (keyword-based, three-branch heuristic) removed entirely
- Step 6 simplified: single plan table with ⚠️ warning, "Proceed?" — no tier choice
- QC-8 (was QC-9) directionality rule now applies to all tests universally
- Old QC-8 (`rollback_risk`) removed; QC-9 renumbered to QC-8
- Requests for read-only state checks (e.g., "show me OSPF neighbor states") → agent asks user to be more specific about what condition to test
- Test scenarios updated: Q1–Q10, legacy tier-specific scenarios removed

### Knowledge Base — BGP and EIGRP Protocol Coverage

- Added `rfc4271_bgp.md`: BGP-4 core — FSM, message types, path attributes, decision process, NOTIFICATION errors, timers
- Added `rfc4760_mpbgp.md`: MP-BGP extensions — MP_REACH_NLRI, MP_UNREACH_NLRI, AFI/SAFI, capability advertisement
- Added `rfc7868_eigrp.md`: EIGRP — DUAL algorithm, packet types, RTP, classic/wide metrics, stub routing, SIA handling
- `_RFC_PROTOCOL_MAP` updated: `rfc4271` → bgp, `rfc4760` → bgp, `rfc7868` → eigrp
- Added vendor BGP guides: Cisco IOS, Arista EOS, Juniper JunOS, Aruba AOS-CX, MikroTik RouterOS, VyOS
- Added vendor EIGRP guide: Cisco IOS
- Fixed `extract_metadata` to handle single-part vendor names (e.g., `vyos`) — protocol is now always the last filename segment
- KB document count: 8 → 18 (5 RFCs + 6 OSPF guides + 6 BGP guides + 1 EIGRP guide)
- KB chunk count: ~199 → ~531 after re-ingestion

---

## v1.1 — 2026-03-31

### Skill: `/qa` — General QA Skill (replaces `/ospf-adj`)

- New general-purpose skill replacing the protocol-specific `/ospf-adj` skill
- Handles any protocol, any feature, any test type from a natural language request
- Protocol, feature, device scope, and tier all derived dynamically from free-form input
- Tier determination logic (Step 1):
  - Explicit active keywords ("active", "configure", "inject", "force", "simulate", "mismatch test", "negative test") → Tier 2 only, no clarification
  - Explicit read-only keywords ("verify", "check", "confirm", "read-only") → Tier 1 only, no clarification
  - Otherwise → assess tier-2 eligibility; if eligible, offer both tiers at Step 6 (Case B)
- Step 6 mandatory pause: test plan presented to user before any files are generated
- 9 quality controls (QC-1 through QC-9): RFC grounding, bidirectionality, vendor CLI, assertion specificity, tier 2 completeness, and tier 2 directionality
- Legacy `/ospf-adj` skill archived to `metadata/legacy/ospf-adj/SKILL.md`

### Tier 2 Active Tests

- New test tier: configure-wait-check-teardown lifecycle
- `setup` block: target device, config command, pre-flight snapshot (CLI + field + expected value)
- `wait` block: post-config convergence delay (type: convergence / fixed / poll, seconds)
- `teardown` block: revert command, verify rollback succeeded (CLI + field + expected value)
- `teardown.verify_expected` must equal `setup.snapshot_expected` — both sourced from INTENT.json
- `rollback_risk` field per test: `low` (timers, cost, priority), `medium` (auth, area type), `high` (redistribution, route policy, router-id)
- Pytest renderer: `try/finally` wrapper — teardown always runs regardless of test outcome
- Session-level rollback registry in `conftest.py` — emergency rollback on interrupted test runs
- Ansible renderer: `block/always` pattern — teardown in `always` block
- Emergency rollback playbook (`playbook_<skill>_rollback.yml`) generated alongside any tier 2 playbook
- QC-9 tier 2 directionality: cross-vendor pairs (different `cli_style`) generate tests in BOTH directions; same-vendor pairs generate ONE direction only

### Knowledge Base — Vendor Doc Updates

- Added "Configuration Revert Patterns" section to all 6 vendor guides
- **Cisco IOS / IOS-XE**: `no <command>` pattern with exception table — auth requires two-step removal, `area stub no-summary` distinct from `area stub`, router-id change requires `clear ip ospf process` on some IOS-XE versions
- **Arista EOS**: `no <command>` OR `default <command>` (factory reset to platform default)
- **Juniper JunOS**: `delete <config-path>` + `commit`; built-in `rollback <n>` config versioning; `commit confirmed <minutes>` safety net; ABR default-metric required for stub/NSSA default route
- **Aruba AOS-CX**: verified from official docs — `no area <id> nssa no-summary` is partial revert only (use `no area <id> nssa` for full removal); `ip ospf shutdown` ≠ remove interface from area; `no ip ospf message-digest-key` requires KEY-ID argument
- **MikroTik RouterOS**: `set <id> <param>=` (empty string = revert to default); `remove <id>` for object-model entries
- **VyOS**: `delete <config-path>` + `commit`; `commit-confirm <minutes>` safety net; `passive [disable]` is a per-interface override when `passive-interface default` is active
- KB chunk count: ~170 → ~199 after re-ingestion (pre-BGP/EIGRP vendor guides)

### Context Window and Token Cost Optimizations

- **Scoped intent queries**: `query_intent("<device>")` per named device instead of full topology dump; 2-device scoped run: ~24 KB → ~2.4 KB intent input (−90%)
- **Schema / renderer split**: `spec-format.md` (14.5 KB) split into:
  - `spec-schema.md` (4 KB) — loaded at Step 7, before YAML generation
  - `spec-renderers.md` (5.3 KB) — loaded at Step 9, before rendering
- **Lazy loading**: each file gated to the step that needs it — renderer patterns absent during spec generation (highest hallucination risk step)
- Total spec + intent overhead: −70% for scoped runs; estimated cost −60% on Sonnet 4.6

### Documentation

- `OPTIMIZATIONS.md` — new section: Context Window and Token Cost Optimizations (before/after numbers, recommended next steps)
- `testing/test_scenarios.md` — rebuilt: S1–S10 legacy `/ospf-adj` scenarios archived; Q1–Q8 `/qa` scenarios covering Tier 1, Tier 2, dual-tier offering, QC-9 cross-vendor and same-vendor directionality
- `metadata/workflow/WORKFLOW.md` — updated to reflect `/qa` skill, Tier 2 lifecycle, current output pipeline, and file loading sequence
- `metadata/legacy/ospf-adj/SKILL.md` — legacy skill preserved as reference

---

## v1.0 — 2026-03-30

Initial release.

### MCP Server (`server.py`)

- 3 tools: `search_knowledge_base`, `query_intent`, `list_devices`
- Pydantic-validated inputs with typed enums for vendor, topic, protocol, cli_style
- Lazy-init ChromaDB with thread-safe singleton
- Compound metadata filtering (`$and` for multi-field queries)

### RAG Pipeline (`ingest.py`)

- 8 knowledge base documents: 2 RFCs (2328, 3101) + 6 vendor guides (Cisco IOS, Arista EOS, Juniper JunOS, Aruba AOS-CX, MikroTik RouterOS, VyOS)
- `all-MiniLM-L6-v2` embeddings (384 dimensions), ChromaDB HNSW index
- Metadata: `vendor`, `topic`, `source`, `protocol` — auto-derived from filenames
- Contextual chunk headers prepended for embedding quality
- `RecursiveCharacterTextSplitter` with Markdown header separators (800 chars, 100 overlap)

### Network Intent (`data/INTENT.json`)

- 16 devices across 4 autonomous systems
- 11 OSPF routers (4 leaf, 2 ABR, 2 core, 1 DC, 2 edge), 19 adjacency pairs
- 2 EIGRP-only routers, 3 BGP-only routers
- 6 platforms: Cisco IOS-XE, Arista EOS, Juniper JunOS, Aruba AOS-CX, MikroTik RouterOS, VyOS (FRR)
- Dual-area ABRs (D1C, D2B) with `area_types` dict; leaf routers with `area_type` string

### Skill: `/ospf-adj`

- 8-step workflow: preflight, spec format load, pair extraction, KB research, YAML spec generation, pytest render, Ansible render, summary
- 8 test criteria (ADJ-01 through ADJ-08): Interface Up, Neighbor Presence, State FULL, Area ID Match, Timer Match, Stub Agreement, MTU Match, Router ID Unique
- Scoped output: 1 device = OR (all pairs for that device), 2+ devices = AND (pairs between listed devices only)
- Canonical filenames with sorted device suffix
- cli_style to KB vendor mapping table for accurate RAG queries
- Per-device test ID pattern for ADJ-08; pair-based for all others
- 6 quality controls (QC-1 through QC-6) enforced during generation

### Shared Schema (`spec-format.md`)

- YAML test spec schema with device, peer, context, query, assertion fields
- 8 assertion types: interface_up, neighbor_presence, neighbor_state, timer_match, area_match, stub_agreement, mtu_match, router_id_unique
- Pytest renderer guidance: scrapli platform mapping, session-scoped fixtures, JUnit XML output
- Ansible renderer guidance: `cli_command` module, `ansible_network_os` mapping, RFC traceability via `vars.rfc`

### Output Structure

- `output/spec/` — canonical YAML test specifications
- `output/pytest/` — scrapli-based pytest suites with `conftest.py`
- `output/ansible/` — Ansible playbooks with `inventory.yml`

### Documentation

- `CLAUDE.md` — agent system prompt (tools, quality standards, data model)
- `metadata/workflow/WORKFLOW.md` — end-to-end test generation flow
- `metadata/scalability/OPTIMIZATIONS.md` — RAG precision roadmap (9 optimizations, 2 implemented)
- `testing/test_scenarios.md` — 10 manual test scenarios with expected pair/test counts

### Infrastructure

- `Makefile` with `setup`, `install`, `ingest`, `clean` targets
- Python 3.11+ venv (`aiqa/`)
- CPU-only PyTorch for local embeddings
