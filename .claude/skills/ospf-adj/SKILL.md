---
name: ospf-adj
description: "Generate professional, RFC-compliant OSPF adjacency test cases from network design intent. Produces a YAML test specification plus pytest and Ansible renderings."
context: fork
---

# /ospf-adj — OSPF Adjacency Test Generation

You are a network test engineer. Generate a complete, production-grade OSPF adjacency test suite for the network described in `data/INTENT.json`.

## Device Scope

`$ARGUMENTS` accepts a flexible number of device names (space-separated).

- `/ospf-adj` — generate tests for all OSPF adjacency pairs in the topology
- `/ospf-adj D1C` — all pairs where D1C is an endpoint
- `/ospf-adj A1M D2B` — only the pair between A1M and D2B
- `/ospf-adj D1C C1J C2A` — only pairs where both endpoints are in the list (D1C↔C1J, D1C↔C2A, C1J↔C2A)

When filtering:
- **One device**: include all pairs where that device is an endpoint.
- **Two or more devices**: include only pairs where **both** endpoints are in the device list.

**Output filename suffix:** When `$ARGUMENTS` is set, append the sorted device names to output filenames (e.g., `ospf_adjacency_C1J_D1C.yaml`). Full-topology runs use no suffix (e.g., `ospf_adjacency.yaml`). See Steps 4–6 for exact paths.

---

## Workflow

### Step 0 — Preflight

1. Call `list_devices` — verify the MCP server is responding and inventory is loaded.
2. Call `query_intent` (no device arg) — verify full topology is available.
3. Call `search_knowledge_base` with `query="ospf adjacency neighbor state"` — verify the KB is populated and returns results.

If any check fails, stop and report the specific failure to the user.

---

### Step 1 — Load Spec Format

Read `.claude/spec-format.md` — the shared YAML spec schema and pytest/Ansible renderer guidance.

Do not continue until it is loaded.

---

### Step 2 — Extract Adjacency Pairs

1. Call `query_intent` (no device arg) to get the full topology.

2. **Identify OSPF routers** — any router entry that has `igp.ospf` defined. Skip routers with only `igp.eigrp`, `igp.bgp`, or no `igp` at all.

3. **Enumerate pairs** — for each OSPF router R, for each neighbor N in `R.direct_links`: if N is also an OSPF router, add the pair. Deduplicate using canonical alphabetical order (A1M↔D1C, not D1C↔A1M).

4. **Determine area per pair** — take the subnet from `R.direct_links[N].subnet` and find which area that subnet appears in under `R.igp.ospf.areas`. That area ID is the pair's area.

5. **Determine area_type per pair** — two INTENT.json schemas exist:
   - **Leaf routers** (single area): `igp.ospf.area_type` is a string (e.g., `"stub"`).
   - **ABR routers** (multiple areas): `igp.ospf.area_types` is a dict keyed by area_id (e.g., `{"1": "stub"}`).
   - If the router has `area_types`, look up the resolved area_id in that dict.
   - If neither field covers the resolved area (e.g., backbone Area 0 on an ABR), default to `normal`.

6. If `$ARGUMENTS` is set:
   - **One device**: keep pairs where that device is an endpoint.
   - **Two or more devices**: keep only pairs where both devices in the pair are in the argument list.

7. Call `list_devices` to cross-reference `cli_style` and `host` for each device in scope.

8. Present the pair table to the user before proceeding:

| Pair | Subnet | Area | Type | Device A cli_style | Device B cli_style |
|------|--------|------|------|--------------------|--------------------|
| ... | | | | | |

Wait for user confirmation before proceeding to Step 3.

---

### Step 3 — Research

For each unique `cli_style` present in the extracted pairs, call `search_knowledge_base` with:
- `protocol: "ospf"`
- `vendor: <vendor>` (e.g., `"cisco_ios"`, `"arista_eos"`)
- `query: "ospf neighbor show command interface timer area stub mtu"`

For any RFC clarification needed, call `search_knowledge_base` with:
- `topic: "rfc"`
- `protocol: "ospf"`
- `query: <relevant concept>`

**Use the vendor commands returned by RAG to populate `query.ssh_cli` for each test entry. Do not hardcode commands — always use the KB result for the device's `cli_style` as the authoritative source.**

Record: the exact show command per criterion per vendor, and the relevant output field names.

---

### Step 4 — Generate YAML Spec

Apply the criteria below to each pair (or scoped subset). Use the assertion schema columns to populate each test entry in the YAML spec.

**Criteria table:**

| ID | Criterion | Applies to | Bidirectional | assertion.type | assertion.field | assertion.expected | assertion.match_by |
|----|-----------|-----------|:-------------:|----------------|-----------------|--------------------|-------------------|
| ADJ-01 | Interface Up | all pairs | yes — one test per device per pair | `interface_up` | `line_protocol` | `up` | `interface: <local_iface>` |
| ADJ-02 | Neighbor Presence | all pairs | yes — one test per direction (A→B and B→A) | `neighbor_presence` | `neighbor_rid` | `<peer router_id>` | `router_id: <peer_rid>` |
| ADJ-03 | State FULL | all pairs | yes — one test per direction | `neighbor_state` | `state` | `FULL` | `router_id: <peer_rid>` |
| ADJ-04 | Area ID Match | all pairs | yes — one test per device per pair | `area_match` | `area_id` | `<area as dotted quad, e.g. 0.0.0.1>` | `interface: <local_iface>` |
| ADJ-05 | Timer Match | all pairs | no — two entries per pair (hello + dead) | `timer_match` | `hello_interval` / `dead_interval` | `10` / `40` | `interface: <local_iface>` |
| ADJ-06 | Stub Agreement | non-backbone pairs only (area_type = stub) | yes — one test per device per pair | `stub_agreement` | `area_type` | `stub` | `interface: <local_iface>` |
| ADJ-07 | MTU Match | all pairs | yes — one test per device per pair | `mtu_match` | `mtu` | `1500` | `interface: <local_iface>` |
| ADJ-08 | Router ID Unique | per OSPF router (not per pair) | n/a — one test per unique device in scope | `router_id_unique` | `router_id` | `<router_id from intent.igp.ospf.router_id>` | *(process-level, no match_by)* |

**Quality controls — check before writing each test entry:**

- **QC-1:** Every test has `rfc` citing a specific RFC section (e.g., `"RFC 2328 §10.5"`). Search the KB if unsure.
- **QC-2:** ADJ-02 and ADJ-03 produce two entries per pair (A→B and B→A) — never collapse to one.
- **QC-3:** `query.ssh_cli` uses the correct vendor command from Step 3 RAG results for this device's `cli_style`.
- **QC-4:** `assertion.expected` is a specific value — never `null`, `any`, or `not empty`.
- **QC-5:** `assertion.match_by` uses `router_id` from intent for neighbor lookups, not the peer's device name.
- **QC-6:** Test IDs follow `ospf_adj_<ADJ-XX>_<deviceA>_<deviceB>` with deviceA < deviceB alphabetically.

**Output path:**
- Full topology: `output/spec/ospf_adjacency.yaml`
- Scoped run: `output/spec/ospf_adjacency_<sorted_devices>.yaml` (e.g., `ospf_adjacency_C1J_D1C.yaml`)

After writing, report total test count and breakdown by criterion.

---

### Step 5 — Render Pytest

Transform the YAML spec into a pytest test suite following `spec-format.md` renderer guidance.

**Output path:**
- Full topology: `output/pytest/test_ospf_adjacency.py` + `output/pytest/conftest.py`
- Scoped run: `output/pytest/test_ospf_adjacency_<sorted_devices>.py` (conftest.py is shared — do not duplicate it if it already exists)

Key requirements:
- Each test reads its `query.ssh_cli` and `assertion` fields directly from the YAML spec
- `match_by` is used to locate the correct row in command output before asserting
- Include RFC reference and description in test docstring
- Add `--junitxml=output/pytest/results.xml` note in a comment at the top

---

### Step 6 — Render Ansible

Transform the YAML spec into an Ansible playbook following `spec-format.md` renderer guidance.

**Output path:**
- Full topology: `output/ansible/playbook_ospf_adjacency.yml` + `output/ansible/inventory.yml`
- Scoped run: `output/ansible/playbook_ospf_adjacency_<sorted_devices>.yml` (inventory.yml is shared)

Key requirements:
- Use `ansible.netcommon.cli_command` with `network_cli` connection for SSH
- One task per test entry — task name = `[<criterion>] <description>`
- `assert` task validates the expected value with context from `match_by`
- Include `vars: { rfc: "<rfc>" }` annotation per task for traceability

---

### Step 7 — Summary

Present a final summary table:

| Output | Path | Tests |
|--------|------|-------|
| YAML spec | output/spec/ospf_adjacency[_<scope>].yaml | N |
| Pytest suite | output/pytest/test_ospf_adjacency[_<scope>].py | N |
| Ansible playbook | output/ansible/playbook_ospf_adjacency[_<scope>].yml | N |

Include a breakdown by criterion: how many tests per ADJ-XX.

---

## Notes

- All tests are **read-only**. Never generate tests that modify device configuration.
- If a KB search returns no results for a vendor, note it in the spec as a gap and use the most semantically similar vendor's command pattern with a warning comment.
- If the intent data is ambiguous for a pair (e.g., area type not determinable), note it explicitly and ask the user before proceeding.
