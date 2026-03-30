# OSPF on VyOS

## Configuration Syntax

```
set protocols ospf parameters router-id <x.x.x.x>
set protocols ospf area <id> network <A.B.C.D/M>
set protocols ospf area <id> area-type stub [no-summary] [default-cost <value>]
set protocols ospf area <id> area-type nssa [no-summary] [default-cost <value>]
set protocols ospf area <id> area-type nssa translate <always|candidate|never>
set protocols ospf area <id> authentication <plaintext-password|md5>
set protocols ospf area <id> range <prefix/len> [cost <value>] [not-advertise] [substitute <prefix/len>]
set protocols ospf area <id> export-list <acl>
set protocols ospf area <id> import-list <acl>
set protocols ospf area <id> virtual-link <router-id>
set protocols ospf area <id> shortcut <default|disable|enable>
set protocols ospf redistribute <bgp|connected|kernel|rip|static> [metric <value>] [metric-type <1|2>] [route-map <name>]
set protocols ospf summary-address <prefix/len> [tag <value>] [no-advertise]
set protocols ospf aggregation timer <seconds>
set protocols ospf default-information originate [always] [metric <value>] [metric-type <1|2>] [route-map <name>]
set protocols ospf default-metric <value>
set protocols ospf distance global <value>
set protocols ospf distance ospf <external|inter-area|intra-area> <value>
set protocols ospf auto-cost reference-bandwidth <mbps>
set protocols ospf timers throttle spf <delay|initial-holdtime|max-holdtime> <ms>
set protocols ospf refresh timers <seconds>
set protocols ospf passive-interface default
set protocols ospf log-adjacency-changes [detail]
set protocols ospf max-metric router-lsa <administrative|on-shutdown <s>|on-startup <s>>
set protocols ospf maximum-paths <1-64>
set protocols ospf parameters abr-type <cisco|ibm|shortcut|standard>
set protocols ospf parameters rfc1583-compatibility
set protocols ospf neighbor <A.B.C.D> [poll-interval <s>] [priority <value>]
set protocols ospf graceful-restart [grace-period <1-1800>]
set protocols ospf graceful-restart helper enable [router-id <A.B.C.D>]
set protocols ospf graceful-restart helper no-strict-lsa-checking
set protocols ospf graceful-restart helper planned-only
set protocols ospf capability opaque

set protocols ospf interface <iface> area <x.x.x.x | x>
set protocols ospf interface <iface> cost <1-65535>
set protocols ospf interface <iface> network <broadcast|non-broadcast|point-to-multipoint|point-to-point>
set protocols ospf interface <iface> priority <0-255>
set protocols ospf interface <iface> hello-interval <seconds>
set protocols ospf interface <iface> dead-interval <seconds>
set protocols ospf interface <iface> retransmit-interval <seconds>
set protocols ospf interface <iface> transmit-delay <seconds>
set protocols ospf interface <iface> hello-multiplier <1-10>
set protocols ospf interface <iface> authentication plaintext-password <key>
set protocols ospf interface <iface> authentication md5 key-id <id> md5-key <key>
set protocols ospf interface <iface> bandwidth <mbps>
set protocols ospf interface <iface> bfd
set protocols ospf interface <iface> mtu-ignore
set protocols ospf interface <iface> passive [disable]
```

VyOS uses FRRouting (FRR) as its routing stack with a `set`-based hierarchical CLI. There is no explicit OSPF process start command or process ID — the OSPF process starts automatically when the first OSPF-enabled interface is configured. Both `area <id> network <prefix>` statements (CIDR notation, not wildcard masks) and per-interface `interface <iface> area` assignment are supported. Per-interface assignment is more explicit and preferred.

Redistribution is configured with `redistribute` and supports route-map filtering. `kernel` is a VyOS/FRR-specific source that redistributes Linux kernel routes (e.g., routes from non-FRR daemons or directly programmed routes) — not available on IOS, EOS, AOS-CX, or RouterOS. External route summarization is configured under `summary-address` with an optional aggregation delay timer.

## VRF Configuration

```
set vrf name <name> table <id>
set interfaces ethernet <iface> vrf <name>

set vrf name <name> protocols ospf parameters router-id <x.x.x.x>
set vrf name <name> protocols ospf area <id> network <A.B.C.D/M>
set vrf name <name> protocols ospf area <id> area-type stub
```

VRFs are created with `set vrf name <name> table <id>` and assigned a unique routing table ID (immutable after creation). Interfaces are enslaved to a VRF with `set interfaces <type> <iface> vrf <name>`. OSPF inside a VRF uses the same configuration commands with the `set vrf name <name>` prefix — no separate process ID or `vrf` keyword in the OSPF hierarchy itself. VRF-aware show commands:
- `show ip route vrf <name>`
- `show ip ospf vrf <name>`

## Verification Commands

| Command | Purpose |
|---------|---------|
| `show ip ospf` | Process overview: router-id, area summary, SPF stats |
| `show ip ospf neighbor` | Neighbor state, priority, dead time |
| `show ip ospf neighbor detail` | Full neighbor detail: options, DR/BDR, timers, state changes |
| `show ip ospf neighbor <A.B.C.D>` | Single neighbor detail by IP address |
| `show ip ospf interface [<iface>]` | Interface parameters: area, cost, network type, timers, DR/BDR |
| `show ip ospf database` | Full LSDB summary (router, network, summary, external LSAs) |
| `show ip ospf database <type> [<lsid>] [adv-router <rid>\|self-originate]` | Specific LSA type detail |
| `show ip ospf database max-age` | LSAs in MaxAge list |
| `show ip ospf route [detail]` | OSPF-computed routing table (network, router, external sections) |
| `show ip ospf border-routers` | ABR and ASBR reachability |
| `show ip route ospf` | OSPF routes installed in the RIB |

Note: VyOS uses `show ip ospf` (IOS-style with `ip` prefix), unlike JunOS which uses `show ospf` without `ip`.

## VyOS-Specific Defaults and Behaviors

- **Process model**: No process ID and no explicit OSPF start command. OSPF activates on first interface configuration. Router ID configured with `parameters router-id`. ABR model is selectable (`parameters abr-type cisco|ibm|shortcut|standard`) — unique among the vendor set; cisco and ibm models follow RFC 3509 behavior; shortcut allows inter-area routes without traversing the backbone when cheaper.

- **Timer defaults (broadcast/P2P)**: Hello 10s, Dead 40s, Retransmit 5s, Transmit-delay 1s. Same as IOS, EOS, JunOS, AOS-CX, and RouterOS.
- **SPF throttle defaults**: delay 200ms, initial-holdtime 1000ms, max-holdtime 10000ms. Delay and initial-holdtime match EOS/AOS-CX (200/1000 ms); max-holdtime matches IOS (10000 ms). Configure with `timers throttle spf`.
- **Hello-multiplier**: `interface <iface> hello-multiplier <1-10>` sends 1–10 Hellos per second (down to 100ms intervals) for sub-second dead-interval convergence. When in use, hello-interval advertised in packets is set to 0 and not checked against neighbors. Not available on IOS, EOS, or AOS-CX.

- **Reference bandwidth**: 100 Mbps default (Mbps notation, same as IOS/EOS). Configure with `auto-cost reference-bandwidth`. Interface `bandwidth <mbps>` can override the link speed used for cost calculation on a per-interface basis.
- **Interface cost**: Derived from reference bandwidth / interface speed. Set explicitly with `interface <iface> cost`. Default cost is 1 for interfaces at or above reference bandwidth.
- **DR priority**: Default 1. Priority 0 makes the interface ineligible for DR/BDR election. Same as IOS, EOS, and AOS-CX; different from JunOS and RouterOS which default to 128.

- **Administrative distance**: 110 for all OSPF route types. Same as IOS, EOS, and AOS-CX.
- **RFC 1583 compatibility**: Disabled by default. VyOS docs explicitly state `parameters rfc1583-compatibility` "should NOT be set normally." Opposite of IOS, EOS, and JunOS which enable it by default. In mixed-vendor networks, ensure all routers agree to avoid external route preference loops.

- **Authentication**: Plaintext (`plaintext-password`) and MD5 per-interface. Area-wide authentication with `area <id> authentication` covers all interfaces in the area. No SHA variants (unlike AOS-CX and RouterOS).
- **Network types**: broadcast, non-broadcast (NBMA), point-to-multipoint, point-to-point. Same breadth as IOS. Broader than EOS (no NBMA/P2MP) and AOS-CX (broadcast/P2P only). NBMA requires static neighbor configuration with `neighbor <A.B.C.D>`.

- **Graceful restart**: Restart support disabled by default; enable with `graceful-restart [grace-period <s>]` (default 120s). GR helper also disabled by default — must be explicitly enabled with `graceful-restart helper enable`. This differs from IOS, EOS, and JunOS where the helper is on by default.
- **Max-metric router-lsa**: Supports `administrative` (indefinite), `on-startup <s>`, and `on-shutdown <s>`. Same as IOS; more options than EOS/AOS-CX.
- **LSA refresh**: Default 1800 seconds (30 minutes), configurable with `refresh timers`. MaxAge is 3600 seconds (60 minutes). Same defaults as IOS and RouterOS.
- **ECMP**: Maximum equal-cost paths default 64. Configure with `maximum-paths`.
- **NBMA poll-interval**: Default 60 seconds (sent to non-adjacent neighbors). Configure per static-neighbor.
- **Passive interface**: `passive-interface default` marks all interfaces passive; use `interface <iface> passive disable` to re-enable specific interfaces. Passive interfaces advertise the subnet but do not form adjacencies.

## Common Gotchas on VyOS

- No OSPF process ID — VyOS does not use process IDs. Unlike IOS/EOS/AOS-CX, there is no `router ospf <pid>` concept. OSPF is a single global process per VRF.
- `area-type stub` and `area-type nssa` are sub-commands of the area node — not `area <id> stub` as on IOS, EOS, and AOS-CX. No-summary is a flag: `area-type stub no-summary`, not `area stub no-summary`.
- Network statements use CIDR notation (`192.168.1.0/24`), not wildcard masks. There is no wildcard-mask form in VyOS.
- `kernel` as a redistribute source redistributes Linux kernel routing table entries — not a configuration artifact from other routers but routes installed by non-FRR processes on the VyOS box itself. Not available on other vendors.
- RFC 1583 compatibility is disabled by default — opposite of IOS, EOS, and JunOS. In a mixed-vendor network with external routes and multiple ASBRs, a VyOS router may select a different ASBR than IOS/EOS neighbors. Enable consistently or verify behavior.
- Graceful restart helper is disabled by default. In a network where other routers perform graceful restarts and rely on VyOS as a helper, `graceful-restart helper enable` must be explicitly configured. IOS, EOS, and JunOS enable the helper by default.
- `show ip ospf` commands follow IOS-style syntax (with `ip`). JunOS operators should note there is no `show ospf` form.
- `hello-multiplier <n>` sets hellos-per-second (1–10), not an interval in seconds. It is mutually exclusive with `hello-interval` on the same interface. When multiplier is set, hello-interval advertised in packets becomes 0.
- `passive [disable]` is the per-interface override when `passive-interface default` is in effect. It is not `no passive-interface` (IOS) or `passive-interface-exclude` — the VyOS syntax inverts the logic.
- VRF OSPF uses the exact same command set prefixed with `set vrf name <name>`. There is no `vrf` keyword within the OSPF configuration hierarchy and no separate process needed.
- MTU mismatch causes neighbors stuck in EXSTART/EXCHANGE. Use `interface <iface> mtu-ignore` to bypass the check (diagnose and fix the mismatch — do not leave mtu-ignore in production).
