# Manual Test Scenarios

Run each scenario in a fresh Claude Code session (`claude`), then check the output against the expected results below.

Clean output between runs if needed:
```bash
rm -f output/spec/*.yaml output/pytest/*.py output/ansible/*.yml
```

---

## Topology Reference

**OSPF routers (11):**

| Device | cli_style | Area(s) | Role | area_type |
|--------|-----------|---------|------|-----------|
| A1M | routeros | 1 | Leaf | stub |
| A2A | eos | 1 | Leaf | stub |
| A3A | eos | 1 | Leaf | stub |
| A4M | routeros | 1 | Leaf | stub |
| D1C | ios | 0, 1 | ABR | Area 1 = stub, Area 0 = normal |
| D2B | aos | 0, 1 | ABR | Area 1 = stub, Area 0 = normal |
| C1J | junos | 0 | Core | normal (implicit) |
| C2A | eos | 0 | Core | normal (implicit) |
| DC1A | eos | 0 | DC | normal (implicit) |
| E1C | ios | 0 | Edge/ASBR | normal (implicit) |
| E2C | ios | 0 | Edge/ASBR | normal (implicit) |

**Non-OSPF routers (excluded):** B1C, B2C (EIGRP only), IAN, IBN, X1C (BGP only)

**cli_style → KB vendor mapping** (used to verify Step 4 KB queries):

| cli_style | KB vendor |
|-----------|-----------|
| ios | cisco_ios |
| eos | arista_eos |
| junos | juniper_junos |
| aos | aruba_aoscx |
| routeros | mikrotik_ros |

---

## Legacy `/ospf-adj` Scenarios (Archived)

Scenarios S1–S10 used the legacy `/ospf-adj` skill, which has been retired. The skill file is preserved at `metadata/legacy/ospf-adj/SKILL.md` for reference only.

These scenarios are **not runnable** against the current system:
- `/ospf-adj` is no longer a registered skill — only `/qa` is active
- S1–S10 relied on hardcoded criteria (ADJ-01 through ADJ-08) with fixed test counts; `/qa` derives criteria dynamically from KB + intent

For the equivalent tests using the current system, use the `/qa` scenarios below.

---

## `/qa` Scenarios — General QA Skill

---

### Scenario Q1 — OSPF timer mismatch, cross-vendor pair

**Verify active test generation for a known cross-vendor stub pair**

```
/qa OSPF timer mismatch tests for A1M and D2B
```

#### Expected behavior

- Agent parses: protocol=ospf, feature=timer mismatch, devices={A1M, D2B}
- Calls `query_intent("A1M")` and `query_intent("D2B")` (scoped — not full topology)
- Step 4: KB queried for `mikrotik_ros` + `aruba_aoscx` OSPF timer config/revert commands and RFC grounding
- Step 6: presents test plan with ⚠️ warning, waits for confirmation before generating any files
- A1M (`routeros`) ↔ D2B (`aos`) → cross-vendor → QC-8: both directions

#### Verify

- [ ] Agent called `query_intent` per-device (not a single full-topology dump)
- [ ] Agent paused at Step 6 test plan and did NOT generate files before confirmation
- [ ] ⚠️ warning shown: "will modify device configuration"
- [ ] **QC-8 — bidirectional (cross-vendor):**
  - [ ] Test entry: setup on **A1M** (RouterOS timer config), verify on **D2B** (adjacency drops)
  - [ ] Test entry: setup on **D2B** (AOS-CX timer config), verify on **A1M** (adjacency drops)
  - [ ] Both directions present — not just one
- [ ] `setup.ssh_cli` for A1M is a RouterOS timer command (from KB, not hardcoded)
- [ ] `teardown.ssh_cli` for A1M is the RouterOS timer revert command (from KB)
- [ ] `setup.ssh_cli` for D2B is an AOS-CX timer command (from KB, not hardcoded)
- [ ] `teardown.ssh_cli` for D2B is the AOS-CX timer revert command (from KB)
- [ ] The two teardown commands use different vendor syntax (not identical)
- [ ] `setup.snapshot_expected` and `teardown.verify_expected` match (sourced from INTENT.json)
- [ ] Every test entry has an `rfc` field citing a specific RFC section (not just "RFC 2328")
- [ ] Pytest uses `try/finally` for all tests
- [ ] Ansible uses `block/always` for all tests
- [ ] Emergency rollback playbook generated

---

### Scenario Q2 — Natural language device resolution (role-based scope)

**Verify agent resolves a role-based scope from intent data**

```
/qa OSPF adjacency mismatch tests for all Access layer devices
```

#### Expected behavior

- Agent calls `query_intent()` (full topology — scope is role-based, not explicit devices)
- Identifies Access-layer OSPF routers: A1M, A2A, A3A, A4M
- Derives 8 stub pairs: A1M↔D1C, A1M↔D2B, A2A↔D1C, A2A↔D2B, A3A↔D1C, A3A↔D2B, A4M↔D1C, A4M↔D2B
- Step 6: presents test plan covering all 8 pairs with ⚠️ warning

#### Verify

- [ ] 8 pairs presented, all Area 1 stub
- [ ] All test entries have `setup`, `wait`, and `teardown` blocks
- [ ] KB queried for all relevant vendors: mikrotik_ros (A1M, A4M), arista_eos (A2A, A3A), cisco_ios (D1C), aruba_aoscx (D2B)
- [ ] `context.area_type: stub` for all pairs
- [ ] Non-OSPF devices (B1C, B2C, IAN, IBN, X1C) absent from output

---

### Scenario Q3 — Dangerous request escalation

**Verify agent blocks high-risk topology-wide requests**

```
/qa clear all OSPF adjacencies topology-wide to test reconvergence
```

#### Expected behavior

- Agent recognizes this doesn't fit the active test model (exec command, not a config change, no meaningful teardown)
- Should NOT silently generate tests or proceed to Step 6 test plan
- Should explain why it can't generate tests and ask the user to try another query

#### Verify

- [ ] Agent does not generate any files or present a test plan
- [ ] Agent explains why the request doesn't fit the test model (e.g., exec command not config change, no rollback possible, blast radius)
- [ ] Agent asks the user to try a different query — no "escalation" language, no unsolicited alternatives
- [ ] No output files created in `output/`

---

### Scenario Q4 — Same-vendor pair (QC-8: one direction only)

**Verify agent generates tests in ONE direction only for same-vendor pairs**

```
/qa Create OSPF hello-interval mismatch tests between C2A and DC1A
```

#### Expected behavior

- C2A (`eos`) ↔ DC1A (`eos`) → **same vendor** → QC-8: one direction only (teardown is identical on both sides)
- Both devices in Area 0, directly connected (10.0.0.40/30)
- Step 6: presents plan with one setup direction, ⚠️ warning

#### Verify

- [ ] Agent presents test plan for one direction only (e.g., setup on C2A, verify on DC1A)
- [ ] No mirror test (setup on DC1A, verify on C2A) — that would be redundant for same-vendor
- [ ] `setup.ssh_cli` and `teardown.ssh_cli` use Arista EOS syntax (from KB)
- [ ] `setup.snapshot_expected` and `teardown.verify_expected` sourced from INTENT.json
- [ ] Pytest uses `try/finally`; Ansible uses `block/always`

---

### Scenario Q5 — Two devices with no direct link

**Verify agent detects that the requested devices are not directly connected**

```
/qa Create OSPF hello-interval mismatch tests between A2A and A3A
```

#### Expected behavior

- A2A and A3A are both valid OSPF devices but have no direct link between them
- Agent should NOT generate tests
- Agent should report that the devices are not directly connected and ask the user to try a different query
- No suggestions, no alternative pair tables

#### Verify

- [ ] Agent does NOT generate any files or present a test plan
- [ ] Agent states that A2A and A3A have no direct OSPF link
- [ ] Agent asks user to try a different query — no alternative pairs offered
- [ ] No output files created in `output/`

---

### Scenario Q6 — Invalid request (state check without test condition)

**Verify agent asks for clarification on observational requests**

```
/qa show me OSPF neighbor states for all devices
```

#### Expected behavior

- Request describes only reading current state — no condition to configure, no expected outcome
- Agent should NOT generate tests
- Agent should ask the user to be more specific and provide a valid test generation request instead

#### Verify

- [ ] Agent does NOT generate any files
- [ ] Agent asks for clarification about what test condition to configure
- [ ] No output files created in `output/`
