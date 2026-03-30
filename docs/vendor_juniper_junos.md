# OSPF on Juniper JunOS

## Configuration Syntax

```
set protocols ospf area <area-id> interface <interface-name>
set protocols ospf area <area-id> interface <name> metric <cost>
set protocols ospf area <area-id> interface <name> passive
set protocols ospf area <area-id> interface <name> interface-type {p2p | nbma}
set protocols ospf area <area-id> interface <name> priority <0-255>

set protocols ospf area <area-id> interface <name> hello-interval <seconds>
set protocols ospf area <area-id> interface <name> dead-interval <seconds>
set protocols ospf area <area-id> interface <name> retransmit-interval <seconds>
set protocols ospf area <area-id> interface <name> transit-delay <seconds>
set protocols ospf area <area-id> interface <name> poll-interval <seconds>

set protocols ospf area <area-id> interface <name> demand-circuit
set protocols ospf area <area-id> interface <name> flood-reduction
set protocols ospf area <area-id> interface <name> secondary
set protocols ospf area <area-id> interface <name> peer <address>

set protocols ospf area <area-id> stub [no-summaries] [default-metric <cost>]
set protocols ospf area <area-id> nssa [no-summaries] [default-lsa default-metric <metric>]
set protocols ospf area <area-id> area-range <prefix>/<len> [restrict]
set protocols ospf area <area-id> virtual-link neighbor-id <router-id> transit-area <area-id>

set protocols ospf reference-bandwidth <value>
set protocols ospf overload [timeout <seconds>]
set protocols ospf no-rfc-1583
set protocols ospf export <policy-name>
set protocols ospf import <policy-name>
set protocols ospf spf-options delay <ms> holddown <ms> rapid-runs <count>
set protocols ospf spf-options microloop-avoidance post-convergence-path delay <ms>
set protocols ospf database-protection maximum-lsa <number> [warning-only] [warning-threshold <percent>] [ignore-count <n>] [ignore-time <seconds>] [reset-time <seconds>]

set protocols ospf area <area-id> interface <name> authentication simple-password <key>
set protocols ospf area <area-id> interface <name> authentication md5 <key-id> key <secret>
set protocols ospf area <area-id> interface <name> authentication md5 <key-id> key <secret> start-time <datetime>

set protocols ospf traceoptions file <filename>
set protocols ospf traceoptions flag {all | general | normal | policy | route | state | task | timer}
```

JunOS uses hierarchical set-style configuration. Interfaces are assigned to areas directly under `[edit protocols ospf]` — there is no `network` statement or separate interface-level OSPF block. The `passive` keyword and authentication are configured per-interface within the area hierarchy.

Route redistribution requires an explicit `export` routing policy under `[edit policy-options]`. There is no implicit `redistribute` command as on IOS, EOS, or AOS-CX. An `import` policy filters routes from the OSPF RIB into the routing table after SPF calculation.

## VRF (Routing Instance) Configuration

```
set routing-instances <vrf-name> instance-type vrf
set routing-instances <vrf-name> interface <name>
set routing-instances <vrf-name> route-distinguisher <rd>
set routing-instances <vrf-name> vrf-target <rt>
set routing-instances <vrf-name> protocols ospf area <area-id> interface <name>
```

JunOS also supports named OSPF instances (non-VRF) via `set protocols ospf-instance <instance-name> area <area-id> interface <name>`, which allows multiple OSPF processes on the same VRF. This is distinct from VRF-based OSPF under routing-instances.

VRF-aware show commands use `instance <vrf-name>`:
- `show ospf neighbor instance <vrf>`
- `show ospf database instance <vrf>`
- `show ospf interface instance <vrf>`

Named instance show commands use `igp-instance <name>`:
- `show ospf neighbor igp-instance <name>`

## Verification Commands

| Command | Purpose |
|---------|---------|
| `show ospf overview [instance <vrf>]` | Process details: router-id, areas, SPF stats, route preferences |
| `show ospf neighbor [instance <vrf>]` | Neighbor state and adjacency |
| `show ospf neighbor detail [instance <vrf>]` | Full neighbor detail (options, timers, adjacency time) |
| `show ospf interface [instance <vrf>]` | Interface parameters: area, timers, cost, DR/BDR, auth |
| `show ospf interface detail [instance <vrf>]` | Extended interface detail (flood-reduction, BFD, demand-circuit) |
| `show ospf database [instance <vrf>]` | Full LSDB contents |
| `show ospf database summary [instance <vrf>]` | LSA type counts per area |
| `show ospf route [instance <vrf>]` | OSPF-computed routing table (separate from full RIB) |
| `show ospf route abr [instance <vrf>]` | ABR/ASBR reachability |
| `show ospf statistics [instance <vrf>]` | SPF run count and duration |
| `show ospf log [instance <vrf>]` | OSPF event and adjacency change log |
| `show route protocol ospf [table <vrf>]` | OSPF routes in the routing table (separate from `show ospf route`) |
| `show ospf trace` | Current traceoptions output |

Note: JunOS uses `show ospf` with no `ip` prefix.

## JunOS-Specific Defaults and Behaviors

- **Router ID selection**: (1) explicit `router-id` under `[edit routing-options]`, (2) highest IP on `lo0.0`, (3) highest active interface IP. Explicit configuration strongly recommended.
- **Multiple instances**: Named OSPF instances via `ospf-instance <name>` allow multiple OSPF processes on the same VRF without routing-instances. VRF-based OSPF uses `routing-instances`.
- **Export policy required**: JunOS requires an explicit `export` routing policy to redistribute routes into OSPF. There is no implicit `redistribute` command. An `import` policy filters routes from OSPF into the RIB — fundamentally different from the `redistribute` and `distribute-list` approach on IOS, EOS, and AOS-CX.

- **Timer defaults (broadcast/P2P)**: Hello 10s, Dead 40s, Retransmit 5s, Transit-delay 1s. Matches IOS/EOS/AOS-CX broadcast defaults.
- **Timer defaults (NBMA)**: Hello 30s, Dead 120s, Poll 120s. NBMA polling applies to non-adjacent neighbors on multi-access networks.
- **SPF throttle defaults**: delay 200ms, holddown 5000ms, rapid-runs 3. Configure with `spf-options delay <ms> holddown <ms> rapid-runs <count>`.
- **Microloop avoidance**: `spf-options microloop-avoidance post-convergence-path delay <ms>` prevents transient microloops during SPF convergence by computing backup paths before cutting over. Not available on EOS or AOS-CX.

- **Reference bandwidth**: 100 Mbps default (same as IOS/EOS). Configure with `reference-bandwidth <value>` using bps notation: `1g` = 1 Gbps, `10g` = 10 Gbps. (Different from IOS/EOS which use Mbps integers; different from AOS-CX which defaults to 100 Gbps.)
- **Interface cost**: Derived from reference-bandwidth / interface-speed. For a 1G link with default 100 Mbps ref-bw the computed cost would floor to 1. Set explicitly with `metric <value>` per interface.
- **DR priority**: Default **128**. Priority 0 prevents DR/BDR election. IOS, EOS, and AOS-CX all default to priority 1 — a JunOS router will win DR elections by default in mixed-vendor environments.

- **Route preference (AD equivalent)**: OSPF internal = 10, OSPF external = 150. Configure with `preference` and `external-preference` under `[edit protocols ospf]`. Much lower than the 110 default on IOS/EOS/AOS-CX — affects route selection when OSPF competes with other protocols.
- **RFC 1583 compatibility**: Enabled by default. Disable with `no-rfc-1583`. Same default as IOS/EOS; opposite of AOS-CX (which disables it by default). Controls external route preference when multiple ASBRs advertise the same prefix.

- **Authentication**: Simple password (`simple-password`) or MD5 (`authentication md5`) per-interface. MD5 supports key rotation with `start-time` for hitless key transitions. No SHA variants (unlike AOS-CX). Authentication must be set per-interface — there is no global authentication shortcut.
- **OSPFv3 authentication**: OSPFv3 has no built-in authentication mechanism. Uses IPsec via `ipsec-sa <sa-name>` on the interface. Security associations are configured under `[edit security ipsec]`.

- **Graceful restart**: Enabled by default per RFC 3623. Allows non-disruptive control-plane restarts. Also default on EOS and AOS-CX.
- **Overload**: `overload [timeout <seconds>]` sets the overload bit in router LSAs, making this router a transit of last resort. Optional timeout auto-clears the overload bit. Equivalent to `max-metric router-lsa` on IOS, EOS, and AOS-CX.
- **Database protection**: `database-protection maximum-lsa <number>` — no default, must be explicitly set. Supports `warning-only`, `warning-threshold`, `ignore-count`, `ignore-time`, `reset-time` options. More configurable than EOS `max-lsa`.
- **Flooding reduction**: `flood-reduction` per interface (RFC 4136). Suppresses periodic LSA refresh on stable interfaces, reducing unnecessary flooding. Not available on IOS, EOS, or AOS-CX.

- **Network types**: Ethernet defaults to broadcast; serial/tunnel links default to point-to-point. NBMA (`interface-type nbma`) and demand-circuit supported. Broader than EOS (no NBMA or demand-circuit) and AOS-CX (broadcast and point-to-point only).
- **Virtual links**: `area <area-id> virtual-link neighbor-id <router-id> transit-area <area-id>` extends the backbone through a non-backbone transit area for noncontiguous backbone topologies.
- **Multiarea adjacency**: RFC 5185 support via `secondary` keyword on an interface assignment. Allows a single interface to participate in multiple OSPF areas simultaneously.

- **LSA refresh**: Default 50 minutes (3000 seconds). MaxAge = 60 minutes. Flood-reduction suppresses this refresh on stable links.
- **Tracing (debug equivalent)**: `traceoptions` under `[edit protocols ospf]` with flags: `all`, `general`, `normal`, `policy`, `route`, `state`, `task`, `timer`. Output goes to a named file in `/var/log/`, not to the console. Use `show ospf trace` to view. Equivalent to IOS `debug ip ospf` but file-based.

## Common Gotchas on JunOS

- `show ospf` has no `ip` prefix — it is not `show ip ospf` as on IOS, EOS, or AOS-CX.
- JunOS does NOT show OSPF data without `instance` if OSPF runs inside a routing-instance. Always specify the instance name.
- `show ospf overview` is the equivalent of IOS `show ip ospf` — shows router-id, area types, SPF stats, and route preferences.
- `lo0.0` must be explicitly added to an OSPF area to advertise the loopback. It is not included automatically.
- Stub area keyword is `no-summaries` (plural), not `no-summary` as on IOS, EOS, and AOS-CX.
- `interface-type p2p` sets point-to-point network type, not `ip ospf network point-to-point` as on IOS/EOS.
- DR priority default is 128, not 1 — a JunOS router will become DR in mixed-vendor elections unless its priority is explicitly lowered.
- Route preference is 10 internal / 150 external, not 110 like IOS/EOS/AOS-CX — this affects route selection when OSPF competes with BGP or static routes.
- `export` policy is required for route redistribution into OSPF. Missing the export policy is the most common cause of routes not appearing in OSPF. There is no `redistribute` command.
- `reference-bandwidth` uses bps notation (`1g`, `10g`), not Mbps integers as on IOS/EOS.
- NBMA neighbors must be statically configured with `peer <address>` — dynamic neighbor discovery is not used on NBMA interfaces.
- Tracing output goes to a file in `/var/log/`, not the console. Use `show ospf trace` to view current output, or `monitor start <filename>` for live streaming.
- `restrict` on `area-range` is equivalent to IOS `not-advertise` — it suppresses the summary LSA rather than advertising it.
