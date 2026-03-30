# OSPF on Aruba AOS-CX

## Configuration Syntax

```
router ospf <process-id> [vrf <vrf-name>]
    router-id <x.x.x.x>
    area <area-id>
    area <area-id> stub [no-summary]
    area <area-id> nssa [no-summary] [default-information-originate]
    area <area-id> range <prefix>/<mask> [not-advertise] [tag <value>]
    area <area-id> default-metric <cost>
    active-backbone stub-default-route
    default-information originate [always] [metric <value>]
    default-metric <value>
    distance <AD>
    distribute-list prefix <name> {in | out}
    redistribute {bgp | connected | local loopback | static | rip | ospf <process-id>} [route-map <name>]
    passive-interface default
    max-metric router-lsa [on-startup [<seconds>]]
    summary-address <prefix>/<mask> [no-advertise] [tag <value>]
    rfc1583-compatibility
    timers throttle spf start-time <ms> hold-time <ms> max-wait-time <ms>
    timers throttle lsa start-time <ms> hold-time <ms> max-wait-time <ms>
    timers lsa-arrival <ms>
    trap-enable
    disable
!
interface <name>
    ip ospf <process-id> area <area-id>
    ip ospf authentication {message-digest | simple-text | null | keychain | hmac-sha-1 | hmac-sha-256 | hmac-sha-384 | hmac-sha-512}
    ip ospf authentication-key <key>
    ip ospf message-digest-key <id> md5 [{ciphertext | plaintext} <key>]
    ip ospf sha-key <id> sha [{ciphertext | plaintext} <key>]
    ip ospf keychain <keychain-name>
    ip ospf cost <value>
    ip ospf network {broadcast | point-to-point}
    ip ospf priority <0-255>
    ip ospf hello-interval <seconds>
    ip ospf dead-interval <seconds>
    ip ospf retransmit-interval <seconds>
    ip ospf transit-delay <seconds>
    ip ospf passive
    ip ospf bfd
    ip ospf shutdown
```

AOS-CX uses per-interface OSPF area assignment (`ip ospf <pid> area <area-id>`). The `network` statement approach is not used.

## VRF Configuration

```
router ospf <process-id> vrf <vrf-name>
    router-id <x.x.x.x>
    area <area-id>
```

VRF-aware show commands append `vrf <name>` or use `all-vrfs`:
- `show ip ospf neighbors vrf <name>`
- `show ip ospf lsdb vrf <name>`
- `show ip ospf interface vrf <name>`
- `show ip ospf all-vrfs`

## Verification Commands

| Command | Purpose |
|---------|---------|
| `show ip ospf [vrf <name>]` | Process overview: router-id, SPF stats, area summary, GR state |
| `show ip ospf neighbors [vrf <name>]` | Neighbor state (note: plural "neighbors") |
| `show ip ospf neighbors detail [vrf <name>]` | Full neighbor detail (DR/BDR, options, dead timer, retransmit queue) |
| `show ip ospf neighbors summary [vrf <name>]` | Neighbor count by state per interface (quick health check) |
| `show ip ospf interface [vrf <name>]` | Interface OSPF parameters, timers, cost, authentication, DR/BDR |
| `show ip ospf interface brief [vrf <name>]` | Compact one-line-per-interface (area, IP, cost, state, status, flags) |
| `show ip ospf lsdb [vrf <name>]` | Full LSDB contents (note: "lsdb" not "database") |
| `show ip ospf lsdb database-summary [vrf <name>]` | LSA type counts per area |
| `show ip ospf routes [vrf <name>]` | OSPF-computed routing table (separate from full RIB) |
| `show ip ospf border-routers [vrf <name>]` | ABR/ASBR reachability |
| `show ip ospf statistics [vrf <name>]` | Packet drop/error statistics |
| `show ip ospf statistics interface [<iface>] [vrf <name>]` | Per-interface TX/RX packet counts and state changes |
| `show interface brief` | Interface status (note: no "ip" prefix) |

## AOS-CX-Specific Defaults and Behaviors

- **Router ID selection**: (1) explicit `router-id` command, (2) highest loopback IP, (3) highest active interface IP. If no IP address is configured on any interface, OSPF will not form an adjacency.
- **Multiple instances**: Up to 8 OSPF processes per VRF. Process ID range: 1-65535.
- **Interface assignment**: OSPF area is assigned per-interface with `ip ospf <pid> area <area-id>`. No `network` statement.
- **Default VRF**: AOS-CX names its default VRF `default`. When OSPF runs in the default VRF, no `vrf` keyword is needed in show commands.

- **Timer defaults**: Hello 10s, Dead 40s, Retransmit 5s, Transit-delay 1s.
- **SPF throttle defaults**: start-time 200ms, hold-time 1000ms, max-wait-time 5000ms.
- **Reference bandwidth**: 100 Gbps (100,000 Mbps) default. Much higher than IOS/EOS 100 Mbps. Adjust with `reference-bandwidth`.
- **Interface cost default**: 1. Cost is recalculated from reference bandwidth and link speed only if `reference-bandwidth` is explicitly configured. VLAN interfaces always use 1 Gbps as link speed for cost calculation.
- **Router priority**: Default 1. Priority 0 makes the interface ineligible for DR/BDR election.
- **Network type default**: broadcast. Only `broadcast` and `point-to-point` are supported.

- **Administrative distance**: Default 110 for all OSPF route types. Configurable per type with `distance`.
- **RFC 1583 compatibility**: `rfc1583-compatibility` is **disabled by default** (opposite of IOS/EOS where it is enabled). Controls external route preference when multiple ASBRs advertise the same prefix.

- **Authentication**: Supports message-digest (MD5), simple-text, null, keychain (rotating MD5 keys), and SHA variants (hmac-sha-1, hmac-sha-256, hmac-sha-384, hmac-sha-512). SHA authentication is broader than IOS/EOS which only support simple password and MD5.
- **BFD integration**: `ip ospf bfd` on an interface enables BFD for fast failure detection.
- **Graceful restart**: restart-interval default 120s, helper enabled by default, strict-lsa-check enabled by default, ignore-lost-interface configurable.
- **Max-metric router-lsa**: Advertises maximum metric to make this router a last resort. `on-startup` default: 600 seconds.

- **distribute-list**: `distribute-list prefix <name> {in|out}` filters routes from the RIB. **Route-maps are NOT supported** in distribute-list on AOS-CX (only prefix-lists).
- **default-metric**: Default metric for redistributed routes is 25 (range 0-1677214).
- **summary-address**: Summarizes external routes at an ASBR. Only works on ASBRs, not ABRs. ABR inter-area summarization uses `area <id> range`.
- **area default-metric**: Sets the cost of the default-summary LSA injected into stub or NSSA areas (default 1).
- **active-backbone stub-default-route**: Sends default route to stub areas if backbone area has an active loopback link. Enabled by default.

- **disable / ip ospf shutdown**: `disable` under `router ospf` disables the entire OSPF process without removing config. `ip ospf shutdown` on an interface disables OSPF on that interface (sets state to Down) but does not remove the area assignment.
- **Command syntax differences**: `show ip ospf neighbors` (plural), `show ip ospf lsdb` (not `database`), `show interface brief` (no `ip`).

## Common Gotchas on AOS-CX

- **Reference bandwidth is 100 Gbps** (100,000 Mbps), not 100 Mbps like IOS/EOS. This means cost values differ significantly from IOS/EOS for the same link speed. A 1G link has cost 100 on AOS-CX vs cost 1 on IOS/EOS with default settings.
- **RFC 1583 compatibility is disabled by default** — opposite of IOS/EOS. In a mixed-vendor network, ensure `rfc1583-compatibility` is consistent on all routers to avoid routing loops with external routes.
- **distribute-list does NOT support route-maps** — only prefix-lists. Operators accustomed to IOS `distribute-list route-map` syntax will get a config error.
- **Interface cost default is 1**, not derived from interface bandwidth, unless `reference-bandwidth` is explicitly configured under `router ospf`. Check `show ip ospf interface` to verify actual cost.
- **VLAN interfaces** always use 1 Gbps as link speed for cost calculation, regardless of actual speed, when `reference-bandwidth` is configured.
- The plural `neighbors` in show commands — `show ip ospf neighbors` not `show ip ospf neighbor`.
- `lsdb` keyword instead of `database` for LSDB inspection.
- `show interface brief` has no `ip` prefix (unlike IOS/EOS `show ip interface brief`).
- When running OSPF in the default VRF, omit the `vrf` keyword from show commands.
- `ip ospf shutdown` disables OSPF on an interface but keeps the area assignment. Use `no ip ospf area` to fully remove the interface from OSPF.
- Authentication mismatch produces the same symptom as timer mismatch (neighbor stuck in INIT/DOWN). Check `show ip ospf statistics` for authentication errors, then verify auth type and keys match on both sides.
