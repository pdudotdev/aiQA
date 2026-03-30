# OSPF on Cisco IOS / IOS-XE

## Configuration Syntax

```
router ospf <process-id>
 router-id <x.x.x.x>
 network <network> <wildcard> area <area-id>
 area <area-id> stub [no-summary]
 area <area-id> nssa [no-summary] [no-redistribution] [default-information-originate] [nssa-only]
 area <area-id> nssa translate type7 {always | suppress-fa}
 area <area-id> range <network> <mask> [not-advertise] [cost <value>]
 area <area-id> default-cost <value>
 area <area-id> virtual-link <router-id>
 area <area-id> authentication [message-digest]
 redistribute <protocol> [subnets] [metric <value>] [metric-type <1|2>] [route-map <name>]
 summary-address <network> <mask> [not-advertise] [tag <value>]
 default-information originate [always] [metric <value>] [metric-type <1|2>] [route-map <name>]
 distribute-list {<acl> | prefix <name> | route-map <name>} {in | out}
 distance ospf {intra-area | inter-area | external} <value>
 auto-cost reference-bandwidth <mbps>
 timers throttle spf <start-ms> <hold-ms> <max-wait-ms>
 timers pacing lsa-group <seconds>
 passive-interface <interface>
 log-adjacency-changes [detail]
 compatible rfc1583
 compatible rfc1587
 max-metric router-lsa [on-startup [<seconds>]]
 neighbor <address> [priority <value>] [poll-interval <seconds>]
!
interface <name>
 ip ospf <process-id> area <area-id>
 ip ospf cost <value>
 ip ospf network {broadcast | non-broadcast | point-to-point | point-to-multipoint [non-broadcast]}
 ip ospf priority <0-255>
 ip ospf hello-interval <seconds>
 ip ospf dead-interval <seconds>
 ip ospf retransmit-interval <seconds>
 ip ospf transmit-delay <seconds>
 ip ospf authentication [message-digest | null]
 ip ospf authentication-key <key>
 ip ospf message-digest-key <id> md5 <key>
 ip ospf demand-circuit
 ip ospf flood-reduction
 ip ospf database-filter all out
 ip ospf mtu-ignore
```

IOS/IOS-XE supports both `network` statements under `router ospf` and per-interface `ip ospf <pid> area <area-id>` assignment. The per-interface method is more explicit and preferred in modern configs. The process ID is locally significant — it does not need to match between neighbors.

The `network` statement uses wildcard masks (not subnet masks) and is evaluated sequentially — the first matching statement determines the area. Running-config stores statements in the order entered. Per-interface `ip ospf area` assignment takes precedence over any matching `network` statement.

## VRF Configuration

```
router ospf <process-id> vrf <vrf-name>
 router-id <x.x.x.x>
 network <network> <wildcard> area <area-id>
```

The `vrf` keyword is added at the process declaration. VRF-aware show commands append `vrf <name>`:
- `show ip ospf neighbor vrf <name>`
- `show ip ospf database vrf <name>`
- `show ip ospf interface vrf <name>`

Default VRF show commands display OSPF data from all VRFs. Specify `vrf <name>` to isolate a single instance.

## Verification Commands

| Command | Purpose |
|---------|---------|
| `show ip ospf` | Process overview: router-id, SPF stats, area summary, timers |
| `show ip ospf neighbor` | Neighbor state, router-id, interface, dead time |
| `show ip ospf neighbor detail` | Full neighbor detail (options, DR/BDR, retransmit queue, dead timer) |
| `show ip ospf interface` | Per-interface: area, timers, network type, cost, auth, passive, DR/BDR |
| `show ip ospf interface brief` | Compact one-line-per-interface summary |
| `show ip ospf database` | Full LSDB — all LSA types with age, router-id, sequence |
| `show ip ospf database database-summary` | LSA type counts per area |
| `show ip ospf border-routers` | ABR and ASBR reachability |
| `show ip ospf virtual-links` | Virtual link state and parameters |
| `show ip ospf summary-address` | External route summarization status |
| `show ip ospf route` | OSPF-computed routes (separate from full RIB) |
| `show ip route ospf` | OSPF routes installed in the RIB |
| `show running-config \| section ospf` | Current OSPF configuration |

## IOS-Specific Defaults and Behaviors

- **Router ID selection**: (1) explicit `router-id` command, (2) highest loopback IP, (3) highest active physical interface IP. Process ID is locally significant and does not need to match on neighbors. From IOS XE 17.13.1a, router-id changes take effect immediately without `clear ip ospf process`; on earlier releases, a process reset is required.

- **Timer defaults (broadcast/P2P)**: Hello 10s, Dead 40s, Retransmit 5s, Transmit-delay 1s. Same as EOS, JunOS, and AOS-CX.
- **Timer defaults (NBMA)**: Hello 30s, Dead 120s, Poll 120s. Static neighbors configured with `neighbor <address>` under `router ospf`.
- **SPF throttle defaults**: 5000 ms start, 10000 ms hold, 10000 ms max-wait. Significantly higher than EOS/AOS-CX (200/1000/5000 ms) and JunOS (200 ms delay, 5000 ms holddown). Configure with `timers throttle spf` to accelerate convergence.
- **LSA group pacing**: 240 seconds (4 minutes) default. Batches LSA refreshes to reduce CPU and bandwidth. Configure with `timers pacing lsa-group <seconds>`.

- **Reference bandwidth**: 100 Mbps default. Cost formula: 10^8 / bandwidth-in-bps. Configure with `auto-cost reference-bandwidth <mbps>` (same Mbps integer notation as EOS; different from JunOS which uses bps notation like `1g`). All interfaces at or above 100 Mbps get cost 1 unless reference bandwidth is raised.
- **Interface cost**: Derived from reference bandwidth / interface speed. On interfaces without bandwidth configured, cost defaults to 1.
- **DR priority**: Default 1. Priority 0 makes the interface ineligible for DR/BDR. Same as EOS and AOS-CX; different from JunOS and RouterOS which default to 128.

- **Administrative distance**: 110 for all OSPF route types (intra-area, inter-area, external). Configurable per type with `distance ospf intra-area <n> inter-area <n> external <n>`. Same as EOS and AOS-CX; lower than JunOS (10/150).
- **RFC 1583 compatibility**: Enabled by default (`compatible rfc1583`). Controls external route preference when multiple ASBRs advertise the same prefix. Same default as EOS and JunOS; opposite of AOS-CX.
- **RFC 1587 NSSA compatibility**: Enabled by default (`compatible rfc1587`). Controls NSSA external route handling. The `nssa-only` flag restricts Type-7 LSA flooding to the NSSA area; `translate type7 suppress-fa` zeroes the forwarding address.

- **Authentication**: Plaintext (`ip ospf authentication` + `ip ospf authentication-key`) and MD5 (`ip ospf authentication message-digest` + `ip ospf message-digest-key <id> md5`). Area-wide authentication via `area <id> authentication [message-digest]` applies to all interfaces in the area without per-interface config. No SHA variants (unlike AOS-CX and RouterOS).

- **Network types**: broadcast (Ethernet, Token Ring, FDDI), non-broadcast (Frame Relay, X.25, SMDS), point-to-point (HDLC, PPP), point-to-multipoint, point-to-multipoint non-broadcast. Broadest network type support among the vendor set; EOS does not support NBMA or point-to-multipoint.
- **Demand circuit**: `ip ospf demand-circuit` suppresses periodic Hello and LSA refresh on the interface (RFC 1793). Designed for DDR and ISDN links to avoid keeping the circuit up.
- **Flood reduction**: `ip ospf flood-reduction` suppresses LSA refresh flooding on stable interfaces (RFC 4136). Reduces unnecessary traffic on stable topologies. Also available on JunOS; not available on EOS or AOS-CX.
- **Database filter**: `ip ospf database-filter all out` blocks all outbound LSA flooding on an interface. Used to create unidirectional adjacencies (e.g., hub-and-spoke NBMA where hub floods to spokes but spokes do not flood back).

- **Graceful restart (NSF)**: NSF helper support enabled by default for both IETF (RFC 3623) and Cisco proprietary graceful restart. The router helps neighbors restart non-disruptively without withdrawing their routes.
- **Max-metric router-lsa**: `max-metric router-lsa` advertises the maximum metric in router LSAs, making this router a last-resort transit path. `on-startup` auto-clears after a configurable number of seconds.
- **Passive interface**: `passive-interface <interface>` suppresses Hello packet transmission and reception on the interface but still advertises the interface's subnet as an OSPF network.
- **LSA refresh**: Every 30 minutes. MaxAge is 60 minutes. LSA group pacing (default 240s) batches refreshes to avoid simultaneous flooding spikes.
- **Redistribution**: `redistribute` requires the `subnets` keyword to include non-classful (subnet) routes. Without `subnets`, only classful network boundaries are redistributed.

## Common Gotchas on IOS

- Forgetting `subnets` on `redistribute` causes only classful networks (e.g., 10.0.0.0/8, not 10.1.1.0/24) to be redistributed — the most common redistribution mistake on IOS.
- `area range` only takes effect on ABR routers. Configuring it on a non-ABR is silently ignored.
- `network` statement uses wildcard masks (`0.0.0.255`), not subnet masks (`255.255.255.0`). Using a subnet mask in the `network` statement produces unexpected area assignments.
- `network` statements are evaluated sequentially — the first match determines the area. Statement order matters; a more specific statement after a less specific one may never match.
- Duplicate router-id causes the EXSTART/EXCHANGE state to loop (EXSTART deadlock). Router ID is unique per process, not globally — two processes on the same box can share a router-id without conflict.
- MTU mismatch causes neighbors stuck in EXSTART or EXCHANGE. `ip ospf mtu-ignore` disables the MTU check in DD packets, but the mismatch should be corrected — the symptom masks a real problem.
- `clear ip ospf process` is required after changing `router-id` on IOS XE releases prior to 17.13.1a. The command drops all adjacencies and is disruptive.
- Auth mismatch produces the same symptom as timer mismatch (neighbor stuck in INIT or fails to reach FULL). Check timer values first with `show ip ospf interface`, then verify auth type and key match on both sides.
- `compatible rfc1583` is enabled by default. In mixed-vendor networks, ensure all routers agree on this setting to avoid external route preference loops.
- `summary-address` summarizes external routes at an ASBR only. For inter-area summarization, use `area <id> range` on an ABR.
- SPF throttle defaults (5s/10s/10s) are much higher than EOS, JunOS, and AOS-CX. Use `timers throttle spf 200 1000 5000` to match EOS/AOS-CX convergence behavior.
