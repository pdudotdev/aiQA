# Manual Test Scenarios for /ospf-adj

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

**Per-pair test counts:**

| Criterion | Backbone pair | Stub pair | Notes |
|-----------|:------------:|:---------:|-------|
| ADJ-01 Interface Up | 2 | 2 | Both devices |
| ADJ-02 Neighbor Presence | 2 | 2 | Both directions |
| ADJ-03 State FULL | 2 | 2 | Both directions |
| ADJ-04 Area ID Match | 2 | 2 | Both devices |
| ADJ-05 Timer Match | 4 | 4 | Both devices x (hello + dead) |
| ADJ-06 Stub Agreement | 0 | 2 | Stub pairs only |
| ADJ-07 MTU Match | 2 | 2 | Both devices |
| **Subtotal per pair** | **14** | **16** | |
| ADJ-08 Router ID Unique | +1 per unique device in scope | | |

---

## Scenario 1 — Single stub pair, cross-vendor

**Tests scope filter (2 devices, AND), stub area, routeros + aos vendor commands**

```
/ospf-adj A1M D2B
```

### Expected

| Check | Expected |
|-------|----------|
| Pairs presented | 1: A1M ↔ D2B |
| Area | 1 (dotted: 0.0.0.1) |
| Area type | stub |
| YAML file | `output/spec/ospf_adjacency_A1M_D2B.yaml` |
| Pytest file | `output/pytest/test_ospf_adjacency_A1M_D2B.py` |
| Ansible file | `output/ansible/playbook_ospf_adjacency_A1M_D2B.yml` |
| Total tests | **18** (16 pair + 2 ADJ-08) |

### Verify in YAML

- [ ] `metadata.pair_count: 1`, `metadata.test_count: 18`
- [ ] ADJ-06 (Stub Agreement) entries **present** for both A1M and D2B
- [ ] A1M tests use routeros CLI commands (e.g., `/routing ospf neighbor print`)
- [ ] D2B tests use AOS-CX CLI commands (e.g., `show ip ospf neighbors`)
- [ ] `assertion.expected` for ADJ-04 is `0.0.0.1` (dotted quad, not `1`)
- [ ] ADJ-02/03 have 2 entries each (A1M→D2B and D2B→A1M), using `match_by.router_id`
- [ ] `match_by.router_id` for A1M→D2B direction = `11.11.11.22` (D2B's RID)
- [ ] `match_by.router_id` for D2B→A1M direction = `1.1.1.1` (A1M's RID)
- [ ] ADJ-05 has 4 entries: hello+dead for A1M, hello+dead for D2B
- [ ] ADJ-08 has 2 entries: `ospf_adj_ADJ-08_A1M` and `ospf_adj_ADJ-08_D2B`
- [ ] Every test has an `rfc` field citing a specific section (not just "RFC 2328")
- [ ] No tests reference B1C, B2C, IAN, IBN, X1C, or any device outside {A1M, D2B}

---

## Scenario 2 — Single backbone pair, same vendor

**Tests backbone (no ADJ-06), same cli_style on both sides (eos + eos)**

```
/ospf-adj C2A DC1A
```

### Expected

| Check | Expected |
|-------|----------|
| Pairs presented | 1: C2A ↔ DC1A |
| Area | 0 (dotted: 0.0.0.0) |
| Area type | normal |
| YAML file | `output/spec/ospf_adjacency_C2A_DC1A.yaml` |
| Total tests | **16** (14 pair + 2 ADJ-08) |

### Verify in YAML

- [ ] ADJ-06 (Stub Agreement) entries **absent** — Area 0 is not stub
- [ ] Both C2A and DC1A tests use Arista EOS commands (e.g., `show ip ospf neighbor`)
- [ ] `assertion.expected` for ADJ-04 is `0.0.0.0`
- [ ] Only 1 KB vendor queried in Step 3 (arista_eos) — both devices are eos
- [ ] DC1A's `router_id` in ADJ-08 is `9.9.9.9`
- [ ] C2A's `router_id` in ADJ-08 is `22.22.22.22`

---

## Scenario 3 — Backbone pair, cross-vendor (JunOS + IOS)

**Tests junos + ios command differentiation on same pair**

```
/ospf-adj C1J D1C
```

### Expected

| Check | Expected |
|-------|----------|
| Pairs presented | 1: C1J ↔ D1C |
| Area | 0 |
| Area type | normal |
| YAML file | `output/spec/ospf_adjacency_C1J_D1C.yaml` |
| Total tests | **16** (14 pair + 2 ADJ-08) |

### Verify in YAML

- [ ] C1J tests use JunOS commands (e.g., `show ospf neighbor`)
- [ ] D1C tests use Cisco IOS commands (e.g., `show ip ospf neighbor`)
- [ ] The two vendors' commands appear in the correct `device` entries (not swapped)
- [ ] D1C's `area_type` resolves to `normal` (Area 0 on an ABR — not in `area_types` dict, so defaults to normal)
- [ ] C1J has no `area_type` or `area_types` field → defaults to `normal`
- [ ] Interfaces: C1J side = `et-0/0/4`, D1C side = `Ethernet1/3`

---

## Scenario 4 — Single device, minimal neighbors

**Tests single-device OR scope with only 1 OSPF neighbor**

```
/ospf-adj DC1A
```

### Expected

| Check | Expected |
|-------|----------|
| Pairs presented | 1: C2A ↔ DC1A |
| YAML file | `output/spec/ospf_adjacency_DC1A.yaml` |
| Total tests | **16** (same as Scenario 2 — same pair) |

### Verify

- [ ] Only 1 pair presented — DC1A has only 1 direct_link to an OSPF router (C2A)
- [ ] The filename suffix is `_DC1A` (single device), not `_C2A_DC1A`
- [ ] Agent did NOT present all 19 pairs (scope filter worked)

---

## Scenario 5 — Single device, hub router (many neighbors)

**Tests single-device OR scope on a hub with many OSPF links, mixed areas**

```
/ospf-adj D1C
```

### Expected

| Check | Expected |
|-------|----------|
| Pairs presented | 7 |
| YAML file | `output/spec/ospf_adjacency_D1C.yaml` |
| Total tests | **114** |

Pair breakdown:

| Pair | Area | Type | Per-pair tests |
|------|------|------|:--------------:|
| A1M ↔ D1C | 1 | stub | 16 |
| A2A ↔ D1C | 1 | stub | 16 |
| A3A ↔ D1C | 1 | stub | 16 |
| A4M ↔ D1C | 1 | stub | 16 |
| C1J ↔ D1C | 0 | normal | 14 |
| C2A ↔ D1C | 0 | normal | 14 |
| D1C ↔ D2B | 0 | normal | 14 |

ADJ-08: 8 unique devices (A1M, A2A, A3A, A4M, C1J, C2A, D1C, D2B) = 8

Total: (4 x 16) + (3 x 14) + 8 = 64 + 42 + 8 = **114**

### Verify in YAML

- [ ] Exactly 7 pairs — B1C and B2C links from D1C are **excluded** (EIGRP, not OSPF)
- [ ] 4 stub pairs have ADJ-06 entries, 3 backbone pairs do not
- [ ] 3 different cli_styles appear: ios (D1C), eos (A2A, A3A, C2A), routeros (A1M, A4M), junos (C1J), aos (D2B) — actually 5 cli_styles
- [ ] KB was queried for all 5 vendors: cisco_ios, arista_eos, mikrotik_ros, juniper_junos, aruba_aoscx
- [ ] ADJ-08 has 8 entries with single-device IDs (e.g., `ospf_adj_ADJ-08_D1C`)

---

## Scenario 6 — Three devices, AND scope filter

**Tests AND filter with 3 devices — only pairs between listed devices**

```
/ospf-adj D1C C1J C2A
```

### Expected

| Check | Expected |
|-------|----------|
| Pairs presented | 3 |
| YAML file | `output/spec/ospf_adjacency_C1J_C2A_D1C.yaml` |
| Total tests | **45** |

Pairs (all backbone/normal):

| Pair | Area | Per-pair tests |
|------|------|:--------------:|
| C1J ↔ C2A | 0 | 14 |
| C1J ↔ D1C | 0 | 14 |
| C2A ↔ D1C | 0 | 14 |

ADJ-08: 3 devices = 3

Total: (3 x 14) + 3 = **45**

### Verify in YAML

- [ ] Exactly 3 pairs — no A1M, A2A, A3A, A4M, D2B, E1C, E2C, DC1A pairs
- [ ] D1C ↔ A1M pair is **absent** even though D1C links to A1M — A1M is not in the device list
- [ ] No ADJ-06 entries (all backbone)
- [ ] Filename suffix has all 3 devices sorted: `_C1J_C2A_D1C`

---

## Scenario 7 — Non-OSPF device (EIGRP only)

**Tests that non-OSPF devices produce 0 pairs**

```
/ospf-adj B1C
```

### Expected

| Check | Expected |
|-------|----------|
| Pairs presented | 0 |
| Output | Agent should report that no OSPF adjacency pairs were found |

### Verify

- [ ] B1C has no `igp.ospf` — agent should detect this and stop or report 0 pairs
- [ ] No YAML/pytest/ansible files generated
- [ ] Agent does NOT crash or generate empty files

---

## Scenario 8 — Two OSPF devices with no direct link

**Tests AND filter where devices exist but share no link**

```
/ospf-adj A1M E1C
```

### Expected

| Check | Expected |
|-------|----------|
| Pairs presented | 0 |
| Output | Agent should report that no adjacency pairs exist between A1M and E1C |

### Verify

- [ ] Both A1M and E1C are valid OSPF routers, but no direct link between them
- [ ] AND filter correctly yields 0 pairs
- [ ] No output files generated

---

## Scenario 9 — Full topology (no arguments)

**Tests full-topology generation — all 19 pairs, all 11 OSPF routers**

```
/ospf-adj
```

### Expected

| Check | Expected |
|-------|----------|
| Pairs presented | 19 |
| YAML file | `output/spec/ospf_adjacency.yaml` (no suffix) |
| Pytest file | `output/pytest/test_ospf_adjacency.py` |
| Ansible file | `output/ansible/playbook_ospf_adjacency.yml` |
| Total tests | **293** |

Breakdown:

| Criterion | Count | Calculation |
|-----------|:-----:|-------------|
| ADJ-01 | 38 | 19 pairs x 2 devices |
| ADJ-02 | 38 | 19 pairs x 2 directions |
| ADJ-03 | 38 | 19 pairs x 2 directions |
| ADJ-04 | 38 | 19 pairs x 2 devices |
| ADJ-05 | 76 | 19 pairs x 2 devices x 2 timers |
| ADJ-06 | 16 | 8 stub pairs x 2 devices |
| ADJ-07 | 38 | 19 pairs x 2 devices |
| ADJ-08 | 11 | 11 unique OSPF routers |
| **Total** | **293** | |

All 19 pairs:

| # | Pair | Area | Type |
|---|------|------|------|
| 1 | A1M ↔ D1C | 1 | stub |
| 2 | A1M ↔ D2B | 1 | stub |
| 3 | A2A ↔ D1C | 1 | stub |
| 4 | A2A ↔ D2B | 1 | stub |
| 5 | A3A ↔ D1C | 1 | stub |
| 6 | A3A ↔ D2B | 1 | stub |
| 7 | A4M ↔ D1C | 1 | stub |
| 8 | A4M ↔ D2B | 1 | stub |
| 9 | C1J ↔ D1C | 0 | normal |
| 10 | C1J ↔ D2B | 0 | normal |
| 11 | C1J ↔ C2A | 0 | normal |
| 12 | C1J ↔ E1C | 0 | normal |
| 13 | C1J ↔ E2C | 0 | normal |
| 14 | C2A ↔ D1C | 0 | normal |
| 15 | C2A ↔ D2B | 0 | normal |
| 16 | C2A ↔ DC1A | 0 | normal |
| 17 | C2A ↔ E1C | 0 | normal |
| 18 | C2A ↔ E2C | 0 | normal |
| 19 | D1C ↔ D2B | 0 | normal |

### Verify in YAML

- [ ] `metadata.pair_count: 19`, `metadata.test_count: 293`
- [ ] 8 stub pairs have ADJ-06, 11 backbone pairs do not
- [ ] Non-OSPF routers (B1C, B2C, IAN, IBN, X1C) appear **nowhere** in the output
- [ ] 5 vendor cli_styles present: ios, eos, junos, aos, routeros
- [ ] Filenames have **no suffix** (full topology)
- [ ] ADJ-08 has exactly 11 entries (one per OSPF router)

### Verify in Pytest

- [ ] `conftest.py` exists with scrapli fixtures
- [ ] Platform mappings correct: ios→cisco_iosxe, eos→arista_eos, junos→juniper_junos, aos→aruba_aoscx, routeros→mikrotik_routeros
- [ ] Test functions reference YAML spec entries
- [ ] No `assert result` or `assert output is not None` (no ghost assertions)

### Verify in Ansible

- [ ] `inventory.yml` has all 11 OSPF routers with correct `ansible_host` and `ansible_network_os`
- [ ] Playbook has `cli_command` tasks, not config-modifying tasks
- [ ] Each task has `vars.rfc` annotation

---

## Scenario 10 — ABR-to-ABR backbone pair

**Tests area resolution for ABR devices on their backbone link**

```
/ospf-adj D1C D2B
```

### Expected

| Check | Expected |
|-------|----------|
| Pairs presented | 1: D1C ↔ D2B |
| Area | 0 (subnet 10.0.0.0/30 is in Area 0 for both) |
| Area type | normal (Area 0 not in either ABR's `area_types` dict → defaults to normal) |
| YAML file | `output/spec/ospf_adjacency_D1C_D2B.yaml` |
| Total tests | **16** (14 pair + 2 ADJ-08) |

### Verify in YAML

- [ ] Area resolved to 0 — D1C and D2B share `10.0.0.0/30` in their Area 0 lists
- [ ] `area_type` is `normal` — **not** `stub` (even though both ABRs have `area_types: {"1": "stub"}`, Area 0 is not in that dict)
- [ ] ADJ-06 (Stub Agreement) **absent** — this is a backbone pair
- [ ] D1C uses ios commands, D2B uses aos commands
- [ ] D1C `router_id` = `11.11.11.11`, D2B `router_id` = `11.11.11.22`

---

## Quick Reference: Run Order

For a full regression, run in this order (simplest to most complex):

| Order | Scenario | Command | Tests | What it validates |
|:-----:|----------|---------|:-----:|-------------------|
| 1 | S7 | `/ospf-adj B1C` | 0 | Non-OSPF exclusion |
| 2 | S8 | `/ospf-adj A1M E1C` | 0 | No-link AND filter |
| 3 | S1 | `/ospf-adj A1M D2B` | 18 | Stub pair, cross-vendor |
| 4 | S2 | `/ospf-adj C2A DC1A` | 16 | Backbone, same vendor |
| 5 | S3 | `/ospf-adj C1J D1C` | 16 | Backbone, cross-vendor |
| 6 | S10 | `/ospf-adj D1C D2B` | 16 | ABR area resolution |
| 7 | S4 | `/ospf-adj DC1A` | 16 | Single-device, 1 neighbor |
| 8 | S6 | `/ospf-adj D1C C1J C2A` | 45 | 3-device AND filter |
| 9 | S5 | `/ospf-adj D1C` | 114 | Single-device hub |
| 10 | S9 | `/ospf-adj` | 293 | Full topology |
