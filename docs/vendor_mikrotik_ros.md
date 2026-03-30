# OSPF on MikroTik RouterOS 7

## Configuration Syntax

RouterOS 7 uses a path-based CLI completely different from IOS-style vendors:

```
/routing ospf instance
add name=<name> router-id=<x.x.x.x> version=<2|3>
set <instance> redistribute=<bgp,connected,copy,dhcp,fantasy,modem,ospf,rip,static,vpn>
set <instance> originate-default=<always|if-installed|never>
set <instance> in-filter=<chain-name>
set <instance> out-filter-chain=<chain-name>
set <instance> out-filter-select=<chain-name>
set <instance> vrf=<routing-table-name>
set <instance> use-dn=<yes|no>

/routing ospf area
add name=<name> instance=<instance> area-id=<x.x.x.x>
set <area> type=<default|stub|nssa>
set <area> no-summaries
set <area> default-cost=<value>
set <area> nssa-translate=<yes|no|candidate>

/routing ospf area/range
add area=<area> prefix=<prefix/len> advertise=<yes|no> cost=<value>

/routing ospf interface-template
add area=<area> networks=<prefix/len> type=<broadcast|nbma|ptp|ptmp|ptp-unnumbered|virtual-link>
set <template> interfaces=<name-or-list>
set <template> cost=<0-65535>
set <template> priority=<0-255>
set <template> hello-interval=<time>
set <template> dead-interval=<time>
set <template> retransmit-interval=<time>
set <template> transmit-delay=<time>
set <template> passive
set <template> auth=<simple|md5|sha1|sha256|sha384|sha512>
set <template> auth-id=<key-id>
set <template> authentication-key=<key>
set <template> instance-id=<0-255>
set <template> prefix-list=<name>
set <template> vlink-neighbor-id=<router-id>
set <template> vlink-transit-area=<area-name>

/routing ospf static-neighbor
add address=<x.x.x.x> area=<area> instance-id=<0-255>
```

Configuration is object-based: instances, areas, and interface-templates are separate objects created and referenced by name. Interface-templates match interfaces using either `networks` (subnet match on interface addresses) or `interfaces` (interface name or list). Both matchers can be used on the same template. The `passive` keyword is a flag on the interface-template, not a separate command.

RouterOS supports both OSPFv2 and OSPFv3 from separate instances using `version=2` or `version=3`. Redistribution uses the `redistribute` parameter directly on the instance object — no export policy or route-map indirection. Outbound filtering uses routing filter chains (`out-filter-chain`, `out-filter-select`) rather than distribute-lists.

## VRF (Routing Table) Configuration

```
/routing table
add name=VRF1 fib

/routing ospf instance
add name=vrf1-ospf router-id=1.1.1.1 vrf=VRF1

/routing ospf area
add name=vrf1-area0 instance=vrf1-ospf area-id=0.0.0.0
```

RouterOS uses "routing tables" as its VRF concept. The `vrf` parameter on the OSPF instance binds it to a routing table (default: `main`). VRFs are defined under `/routing table` with a `fib` flag to install routes into the forwarding plane.

RouterOS OSPF commands do not have VRF-specific show variants. All instances are visible together; filter by instance name to isolate a VRF.

## Verification Commands

| Command | Purpose |
|---------|---------|
| `/routing ospf neighbor print detail without-paging` | Neighbor state, adjacency, DR/BDR, timers |
| `/routing ospf neighbor print terse without-paging` | Compact neighbor table (one line per neighbor) |
| `/routing ospf interface print detail without-paging` | Matched OSPF interfaces (read-only), area, cost, state, DR/BDR |
| `/routing ospf interface print terse without-paging` | Compact matched interface table |
| `/routing ospf interface-template print without-paging` | Interface-template configuration (matchers + assigned params) |
| `/routing ospf lsa print without-paging` | Full LSDB contents (LSA type, originator, ID, age, checksum) |
| `/routing ospf instance print detail without-paging` | Instance details: router-id, version, VRF, redistribute, filters |
| `/routing ospf area print detail without-paging` | Area config: type, instance, default-cost, NSSA translate |
| `/routing ospf area/range print without-paging` | Area range summarization config |
| `/routing ospf static-neighbor print without-paging` | NBMA static neighbor configuration |
| `/ip route print where routing-mark=<table> and ospf` | OSPF routes in a specific routing table |
| `/interface print brief without-paging` | Interface status (note: no `/ip` prefix) |

Note: Always append `without-paging` for scripted/SSH access. Use `terse` for compact tabular output or `detail` for verbose key-value output.

## RouterOS-Specific Defaults and Behaviors

- **Router ID**: Set on the instance with `router-id`. Can be an explicit IP or the name of a `/routing id` instance. Default value is `main`, which uses automatic selection from interface IPs. Explicit configuration is recommended.
- **OSPFv2 and OSPFv3**: Both supported from separate instances using `version=2` (IPv4) or `version=3` (IPv6). Default is version 2.
- **Object-based config**: Instances, areas, and interface-templates are named objects. Areas reference instances by name, templates reference areas by name. This is fundamentally different from the hierarchical CLI of IOS, EOS, JunOS, and AOS-CX.

- **Timer defaults**: Hello 10s, Dead 40s, Retransmit 5s, Transmit-delay 1s. Same as IOS/EOS/JunOS broadcast defaults.
- **Reference bandwidth**: 100 Mbps. Cost formula: `100000000 / bandwidth-in-bps`. Same as IOS/EOS/JunOS. A 1G link = cost 100, a 10G link = cost 10.
- **Interface cost**: Not set by default on interface-templates; when unset, derived from reference bandwidth and link speed. Set explicitly with `cost=<value>`.
- **DR priority**: Default **128** (RFC-defined value). Priority 0 makes the interface ineligible for DR/BDR. Same as JunOS; different from IOS/EOS/AOS-CX which default to 1. Note: RouterOS v6 defaulted to 1 — migrated configs may have strict priority assumptions that break on v7.

- **Administrative distance**: OSPF routes install with distance 110 (same as IOS/EOS/AOS-CX).
- **Network type default**: broadcast on multi-access interfaces, point-to-point on PtP interfaces. Supported types: `broadcast`, `nbma`, `ptp`, `ptmp`, `ptp-unnumbered`, `virtual-link`. Broader than EOS (no NBMA) and AOS-CX (broadcast/ptp only).
- **Point-to-point syntax**: `type=ptp` (not `point-to-point`). Point-to-multipoint is `ptmp`. `ptp-unnumbered` handles IP unnumbered links (e.g., Cisco unnumbered peering).

- **Authentication**: `simple` (plaintext), `md5`, `sha1`, `sha256`, `sha384`, `sha512`. SHA variants use HMAC-SHA per RFC 5709. Broader than IOS/EOS (simple + MD5 only). Set `auth`, `auth-id`, and `authentication-key` on the interface-template.
- **Redistribution**: Configured directly on the instance with `redistribute=<protocols>`. Accepts: `bgp`, `connected`, `copy`, `dhcp`, `fantasy`, `modem`, `ospf`, `rip`, `static`, `vpn`. No route-map indirection needed for basic redistribution.
- **Default route origination**: `originate-default=always` generates a default route unconditionally; `if-installed` only if a default exists in the routing table; `never` (default) suppresses it.
- **Outbound filtering**: `out-filter-chain` filters external LSAs before flooding. `out-filter-select` selects which routes are candidates for redistribution. Both reference routing filter chains defined under `/routing filter rule`. These operate only on external routes, not intra-area or inter-area.

- **Area types**: `default` (standard), `stub`, `nssa`. Totally stubby is `type=stub` with `no-summaries` flag. NSSA-to-type5 translation controlled by `nssa-translate` (`yes`, `no`, `candidate`).
- **Area range summarization**: Configured under `/routing ospf area/range` with `prefix`, `area`, `advertise` (yes/no), and `cost`. When `advertise=no`, the range suppresses the summary LSA (equivalent to IOS `not-advertise`). An active range installs a blackhole route.
- **Virtual links**: Configured as an interface-template with `type=virtual-link`, `vlink-neighbor-id=<router-id>`, and `vlink-transit-area=<area-name>`. Cannot traverse stub or NSSA areas.

- **Static neighbors**: NBMA neighbors configured under `/routing ospf static-neighbor` with `address` and `area`. Required for NBMA and useful for PTMP networks without broadcast capability.
- **use-dn**: Forces use or ignore of the DN bit in LSAs. Useful in CE-PE scenarios to inject intra-area routes into a VRF. Unset by default (follows RFC behavior).
- **LSA refresh**: Every 30 minutes. MaxAge is 60 minutes.

## Common Gotchas on RouterOS

- Forgetting `without-paging` causes SSH sessions to hang waiting for user input.
- The `+ct` suffix on username (e.g., `admin+ct`) disables colors and auto-completion for clean output parsing in automation scripts.
- RouterOS 7 OSPF configuration is completely restructured from RouterOS 6. Old ROS6 commands (`/routing ospf network add`) do not work. The entire config model changed to instance/area/interface-template objects.
- DR priority default changed from 1 (ROS v6) to 128 (ROS v7). Migrated networks with strict DR election priorities may behave differently after upgrade.
- `type=ptp` not `type=point-to-point`. `ptmp` not `point-to-multipoint`. `ptp-unnumbered` is a RouterOS-specific type for IP unnumbered links.
- `terse` flag on `print` gives compact tabular output; `detail` gives verbose key-value output. Neither is the default — plain `print` uses an intermediate format.
- LSA database uses `/routing ospf lsa`, not `database`. The keyword is `lsa` everywhere.
- Interface-template `networks` uses CIDR notation and matches by subnet, not by interface name. Use `interfaces` to match by name or interface list.
- There is no `show` keyword — RouterOS uses `/routing ospf neighbor print` style. All OSPF menus are under `/routing ospf/`.
- `originate-default` interacts with `out-filter-chain` in subtle ways: when set to `always` or `if-installed`, OSPF creates a synthetic default route and runs it through the filter chain, but the filter action (accept/reject) is ignored — the default is always originated. The filter can only set attributes.
- No per-VRF show command variants. All OSPF instances appear together; filter output by instance name to isolate VRF data.
- Area range with `advertise=no` suppresses the summary but also installs a blackhole route. This is the equivalent of IOS `not-advertise` on `area range`.
