# OSPF on Arista EOS

## Configuration Syntax

```
router ospf <process-id>
   router-id <x.x.x.x>
   network <network>/<prefix-len> area <area-id>
   area <area-id> stub [no-summary]
   area <area-id> nssa [no-summary] [default-information-originate]
   area <area-id> range <network>/<prefix-len> [not-advertise]
   area <area-id> default-cost <value>
   area <area-id> filter <subnet>
   area <area-id> filter prefix-list <name>
   passive-interface <interface>
   redistribute <protocol> [route-map <name>]
   distribute-list prefix-list <name> in
   max-lsa <number>
   distance ospf intra-area <n> inter-area <n> external <n>
   log-adjacency-changes [detail]
   compatible rfc1583
   shutdown
!
interface <name>
   ip ospf area <area-id>
   ip ospf cost <value>
   ip ospf network point-to-point
   ip ospf priority <0-255>
   ip ospf bfd
   ip ospf authentication
   ip ospf authentication-key <key>
   ip ospf authentication message-digest
   ip ospf message-digest-key <id> md5 <key>
   ip ospf hello-interval <seconds>
   ip ospf dead-interval <seconds>
   ip ospf disabled
```

EOS supports both `network` statements and per-interface `ip ospf area` assignment. The per-interface method is preferred and more explicit.

EOS accepts both CIDR (`/24`) and wildcard-mask (`0.0.0.255`) notation in `network` statements. Running-config normalizes to CIDR.

## VRF Configuration

```
router ospf <process-id> vrf <vrf-name>
   router-id <x.x.x.x>
   network <network>/<prefix-len> area <area-id>
```

VRF-aware show commands append `vrf <name>` at the end:
- `show ip ospf neighbor vrf VRF1`
- `show ip ospf database vrf VRF1`
- `show ip ospf interface vrf VRF1`

In non-default VRFs, `dn-bit-ignore` controls whether LSAs with the DN bit set are included in SPF calculation. Relevant for MPLS VPN CE-PE topologies where Type-3/5/7 LSAs may carry the DN bit to prevent routing loops.

## Verification Commands

| Command | Purpose |
|---------|---------|
| `show ip ospf neighbor [vrf <name>]` | Neighbor state and adjacency details |
| `show ip ospf neighbor detail [vrf <name>]` | Full neighbor detail (options, DR/BDR, timers, BFD state) |
| `show ip ospf neighbor summary [vrf <name>]` | Neighbor count by state (quick health check) |
| `show ip ospf interface [vrf <name>]` | Interface parameters, timers, area, cost, DR/BDR |
| `show ip ospf interface brief [vrf <name>]` | Compact one-line-per-interface summary (PID, area, IP, cost, state, neighbors) |
| `show ip ospf database [vrf <name>]` | Full LSDB contents |
| `show ip ospf database database-summary [vrf <name>]` | LSA type counts per area |
| `show ip ospf [vrf <name>]` | Process overview, router-id, SPF stats, area summary |
| `show ip ospf route [vrf <name>]` | OSPF-computed routes (separate from full RIB) |
| `show ip ospf spf-log [vrf <name>]` | SPF calculation history and duration |
| `show running-config section ospf` | Current OSPF configuration |

## EOS-Specific Defaults and Behaviors

- **Router ID selection**: (1) explicit `router-id` command, (2) highest loopback IP, (3) highest interface IP. On MLAG with VXLAN, always set `router-id` manually to avoid using the shared VTEP IP.
- **Multiple instances**: EOS supports multiple OSPFv2 instances on the default VRF in multi-agent routing mode. Each instance is identified by a unique process ID.
- **ip routing prerequisite**: OSPFv2 requires `ip routing` to be enabled globally. EOS logs a warning if it is not.

- **Timer defaults**: Hello 10s, Dead 40s, Retransmit 5s, Transmit-delay 1s (broadcast and point-to-point).
- **Reference bandwidth**: 100 Mbps default (same as IOS). Adjust with `auto-cost reference-bandwidth`.
- **Interface cost default**: 10. Cost is not automatically derived from interface bandwidth unless `auto-cost reference-bandwidth` is configured.
- **Router priority**: Default 1. Priority 0 makes the interface ineligible for DR/BDR election.
- **Network type defaults**: Ethernet = broadcast, Tunnel = point-to-point.

- **Administrative distance**: Default 110 for all OSPF route types. Configurable per type with `distance ospf intra-area <n> inter-area <n> external <n>`. Changing AD while OSPF is running causes all OSPF routes to be withdrawn and re-installed.
- **RFC 1583 compatibility**: `compatible rfc1583` is the default. Controls external route preference when multiple ASBRs advertise the same prefix. Disabling uses RFC 2328 rules.

- **Authentication**: Simple password: `ip ospf authentication` + `ip ospf authentication-key` on the interface. MD5: `ip ospf authentication message-digest` + `ip ospf message-digest-key <id> md5 <key>`. By default, no authentication is configured.
- **Max-LSA protection**: `max-lsa` limits LSDB size and protects CPU. Triggers warning at a configurable percentage, temporary shutdown at the limit, and permanent shutdown after repeated overloads.
- **BFD integration**: `ip ospf bfd` on an interface enables BFD for fast failure detection.

- **log-adjacency-changes**: Logs neighbor state transitions to up/down. `detail` variant logs every state change. Recommended for troubleshooting.
- **Graceful restart**: Supported per RFC 3623 for non-disruptive control-plane restarts. Configurable grace period.
- **shutdown / ip ospf disabled**: `shutdown` under `router ospf` disables the entire OSPF process without removing config. `ip ospf disabled` on an interface removes that interface from OSPF.

- **distribute-list**: `distribute-list prefix-list <name> in` filters OSPF routes from the RIB after SPF calculation. Does not affect LSDB flooding. One distribute-list per OSPF instance.
- **area default-cost**: `area <id> default-cost <value>` sets the metric of the default summary route injected into stub or NSSA areas by the ABR.
- **area filter**: `area <id> filter <subnet>` prevents a specific subnet from being advertised as a Type 3 LSA by the ABR.
- **area filter prefix-list**: `area <id> filter prefix-list <name>` filters Type 3 summary LSAs and Type 4 ASBR summary LSAs at an ABR boundary.

- **GRE tunnels**: OSPF routes over GRE tunnels are supported but disabled by default. Enable with `tunnel routes` under `router ospf`. Certain platforms (DCS-7020, 7280R/R2, 7500R/R2) require a TCAM profile with the `tunnel ipv4` feature enabled.
- **Section filter**: EOS uses `section` keyword directly (no pipe): `show running-config section ospf`.

## Unsupported Features

EOS does **not** support: NBMA network type, demand circuits, point-to-multipoint interfaces, OSPFv2 MIB. Do not suggest these during troubleshooting.

## Common Gotchas on EOS

- VRF must be specified in show commands to see VRF-specific OSPF data — `show ip ospf neighbor` without VRF shows only default VRF.
- EOS accepts both CIDR and wildcard-mask notation in `network` statements, but running-config always stores CIDR. Operators accustomed to IOS wildcard-only syntax should note both formats work.
- Interface-level `ip ospf area` takes precedence over `network` statements under `router ospf`.
- On multi-chassis (MLAG) setups, ensure OSPF router-id is unique per chassis and does not collide with the shared VTEP IP.
- `shutdown` under `router ospf` silently disables all OSPF activity — check this early when all neighbors are DOWN.
- `ip routing` must be enabled globally; OSPF will not form adjacencies without it. The warning is easy to miss in config output.
- Changing `distance ospf` while OSPF is active causes all OSPF routes to be withdrawn and re-installed, triggering a brief routing disruption.
- Authentication mismatch produces the same symptom as timer mismatch (neighbor stuck in INIT/DOWN). Check timers first, then verify authentication type and keys match on both sides.
