# BGP on VyOS

VyOS uses FRRouting (FRR) as its routing stack. All BGP behavior is FRR behavior exposed through the `set protocols bgp` CLI hierarchy.

## Configuration Syntax

### System AS and Router ID

```
set protocols bgp system-as <asn>
set protocols bgp parameters router-id <x.x.x.x>
```

There is no `router bgp` command — the BGP process starts automatically when the first neighbor is configured. Router ID defaults to the highest interface IP address if not set explicitly; always configure it manually.

### Neighbor Definition

```
set protocols bgp neighbor <ip> remote-as <asn>
set protocols bgp neighbor <ip> remote-as internal          ! deny if remote ASN != local ASN
set protocols bgp neighbor <ip> remote-as external          ! deny if remote ASN == local ASN
set protocols bgp neighbor <ip> remote-as auto              ! detect remote ASN from OPEN message
set protocols bgp neighbor <ip> local-role <role> [strict]  ! RFC 9234: provider|customer|peer|rs-server|rs-client
set protocols bgp neighbor <ip> update-source <address|interface>
set protocols bgp neighbor <ip> description <text>
set protocols bgp neighbor <ip> password <text>
set protocols bgp neighbor <ip> shutdown
set protocols bgp neighbor <ip> passive                     ! wait for incoming TCP, don't initiate
set protocols bgp neighbor <ip> ebgp-multihop <ttl>         ! 1-255; mutually exclusive with ttl-security
set protocols bgp neighbor <ip> ttl-security hops <n>       ! GTSM; mutually exclusive with ebgp-multihop
set protocols bgp neighbor <ip> disable-connected-check     ! allow eBGP over loopbacks without adjusting TTL
set protocols bgp neighbor <ip> advertisement-interval <seconds>   ! default 0
set protocols bgp neighbor <ip> local-as <asn> [no-prepend] [replace-as]   ! eBGP only
set protocols bgp neighbor <ip> solo                        ! prevent re-advertising prefixes back to this peer
set protocols bgp neighbor <ip> disable-send-community <extended|standard>  ! default: communities ARE sent
```

Note: `local-as`, `ebgp-multihop`, and `ttl-security` are eBGP-only options.

`strict` on `local-role` requires the peer to also declare a role in its OPEN before the session is allowed to establish.

### Address-Family Activation and Per-Neighbor Policy

```
set protocols bgp neighbor <ip> address-family ipv4-unicast
set protocols bgp neighbor <ip> address-family ipv4-unicast activate          ! (implicit when AF block exists)
set protocols bgp neighbor <ip> address-family ipv4-unicast nexthop-self
set protocols bgp neighbor <ip> address-family ipv4-unicast route-reflector-client
set protocols bgp neighbor <ip> address-family ipv4-unicast route-map <export|import> <name>
set protocols bgp neighbor <ip> address-family ipv4-unicast prefix-list <export|import> <name>
set protocols bgp neighbor <ip> address-family ipv4-unicast filter-list <export|import> <name>
set protocols bgp neighbor <ip> address-family ipv4-unicast distribute-list <export|import> <number>
set protocols bgp neighbor <ip> address-family ipv4-unicast default-originate [route-map <name>]
set protocols bgp neighbor <ip> address-family ipv4-unicast soft-reconfiguration inbound
set protocols bgp neighbor <ip> address-family ipv4-unicast allowas-in number <n>   ! eBGP only, not peer groups
set protocols bgp neighbor <ip> address-family ipv4-unicast as-override             ! eBGP only
set protocols bgp neighbor <ip> address-family ipv4-unicast attribute-unchanged <as-path|med|next-hop>
set protocols bgp neighbor <ip> address-family ipv4-unicast maximum-prefix <n>
set protocols bgp neighbor <ip> address-family ipv4-unicast remove-private-as       ! eBGP only
set protocols bgp neighbor <ip> address-family ipv4-unicast weight <n>              ! 1-65535
set protocols bgp neighbor <ip> address-family ipv4-unicast unsuppress-map <name>
set protocols bgp neighbor <ip> address-family ipv4-unicast capability orf <receive|send>
```

VyOS uses `export`/`import` (not `out`/`in`) for direction in route-map, prefix-list, and filter-list. `prefix-list` and `distribute-list` are **mutually exclusive** per neighbor per direction.

### Network Advertisement and Redistribution

```
set protocols bgp address-family ipv4-unicast network <prefix>
set protocols bgp address-family ipv4-unicast network <prefix> backdoor
set protocols bgp address-family ipv4-unicast aggregate-address <prefix>
set protocols bgp address-family ipv4-unicast aggregate-address <prefix> summary-only
set protocols bgp address-family ipv4-unicast aggregate-address <prefix> as-set
set protocols bgp address-family ipv4-unicast redistribute <connected|kernel|ospf|rip|static|table>
set protocols bgp address-family ipv4-unicast redistribute <source> route-map <name>
set protocols bgp address-family ipv4-unicast redistribute <source> metric <n>
set protocols bgp address-family ipv4-unicast maximum-paths ebgp <n>
set protocols bgp address-family ipv4-unicast maximum-paths ibgp <n>
```

`backdoor` makes the router prefer an IGP route over an eBGP route for the same prefix (lowers the prefix AD to internal BGP distance).

Without `summary-only`, both the aggregate and more-specific routes are advertised.

### Global BGP Parameters

```
set protocols bgp parameters router-id <x.x.x.x>
set protocols bgp parameters log-neighbor-changes
set protocols bgp parameters no-fast-external-failover          ! disable; fast-failover is ON by default
set protocols bgp parameters no-client-to-client-reflection     ! disable C2C on RR; enabled by default
set protocols bgp parameters no-hard-administrative-reset
set protocols bgp parameters ebgp-requires-policy               ! enforce RFC 8212; disabled by default
set protocols bgp parameters allow-martian-nexthop
set protocols bgp parameters no-ipv6-auto-ra
set protocols bgp parameters cluster-id <id>                    ! RR cluster ID; defaults to router-id
set protocols bgp parameters default local-pref <n>             ! default 100
set protocols bgp parameters always-compare-med
set protocols bgp parameters deterministic-med
set protocols bgp parameters bestpath as-path ignore
set protocols bgp parameters bestpath as-path multipath-relax
set protocols bgp parameters bestpath as-path confed
set protocols bgp parameters bestpath compare-routerid
set protocols bgp parameters bestpath med confed
set protocols bgp parameters bestpath med missing-as-worst
set protocols bgp parameters confederation identifier <asn>
set protocols bgp parameters confederation peers <sub-asn>
set protocols bgp parameters network-import-check               ! require prefix to exist in RIB for network statement
set protocols bgp parameters dampening half-life <minutes>      ! 10-45
set protocols bgp parameters dampening re-use <seconds>         ! 1-20000
set protocols bgp parameters dampening start-suppress-time <seconds>
set protocols bgp parameters dampening max-suppress-time <minutes>
```

### Timers

```
set protocols bgp timers holdtime <seconds>    ! default 180; range 4-65535; 0 = never expire
set protocols bgp timers keepalive <seconds>   ! default 60; range 4-65535
```

### Dynamic Peers / Listen Range

```
set protocols bgp listen range <prefix> peer-group <name>
set protocols bgp listen limit <n>             ! max simultaneous dynamic peers; 1-5000
```

The peer-group must be defined or `commit` will fail.

### Administrative Distance

```
set protocols bgp parameters distance global external <1-255>
set protocols bgp parameters distance global internal <1-255>
set protocols bgp parameters distance global local <1-255>
set protocols bgp parameters distance prefix <subnet> distance <1-255>
```

Routes with distance 255 are not installed in the kernel.

### Peer Groups

```
set protocols bgp peer-group <name>
set protocols bgp neighbor <ip> peer-group <name>
```

Capability negotiation options per neighbor: `capability dynamic`, `capability extended-nexthop` (auto-enabled on IPv6 link-local peerings; enables IPv4 NLRIs with IPv6 next-hops per RFC 5549), `disable-capability-negotiation` (disables BGP unnumbered, AS4, Add-Path, Route Refresh, graceful restart — only for very old peers), `override-capability`, `strict-capability-match`.

VRF configuration uses `set protocols bgp vrf <vrf-name> ...`; show commands append `vrf <name>`.

## Verification Commands

In **operational mode** these are used directly. In **config mode** prefix with `run`:

| Command | Purpose |
|---------|---------|
| `show bgp ipv4 summary` | All peer states: AS, MsgRcvd, MsgSent, Up/Down, State/PfxRcd |
| `show bgp ipv4` | Full IPv4 BGP table with status codes, next-hop, metric, localpref, AS-path |
| `show bgp ipv4 <prefix>` | Detail for a specific prefix: all paths, best-path selection, attributes |
| `show bgp ipv4 neighbors <ip>` | Detailed peer state: timers, capabilities, counters |
| `show bgp ipv4 neighbors <ip> advertised-routes` | Routes advertised to a specific peer (after outbound policy) |
| `show bgp ipv4 neighbors <ip> received-routes` | Routes received before inbound policy (requires `soft-reconfiguration inbound`) |
| `show bgp ipv4 neighbors <ip> routes` | Routes accepted from peer (after inbound policy) |
| `show bgp ipv4 community <value>` | Routes matching a community value |
| `show bgp ipv4 community-list <name>` | Routes permitted by a community list |
| `show bgp ipv4 regexp <regex>` | Routes matching an AS-path regular expression |
| `show bgp ipv4 filter-list <name>` | Routes allowed by an AS-path access list |
| `show bgp ipv4 dampening dampened-paths` | Currently dampened routes |
| `show bgp ipv4 dampening flap-statistics` | Route flap statistics |
| `show bgp ipv4 neighbors <ip> dampened-routes` | Dampened routes from a specific peer |
| `show bgp cidr-only` | Routes with CIDR (non-classful) notation |

Note: VyOS uses `show bgp ipv4` (not `show ip bgp` as on IOS/EOS). The address-family qualifier is part of the command.

**`show bgp ipv4` status codes**:
```
Status codes: s suppressed, d damped, h history, * valid, > best, = multipath, i internal,
              r RIB-failure, S Stale, R Removed
Origin codes: i IGP, e EGP, ? incomplete
```

**Session reset commands (operational mode)**:

| Command | Effect |
|---------|--------|
| `reset bgp ipv4 <ip>` | Hard reset — tears down TCP session, full re-exchange |
| `reset bgp ipv4 <ip> soft in` | Soft inbound reset — re-applies inbound policy without dropping session |
| `reset bgp ipv4 <ip> soft out` | Soft outbound reset — re-sends routes with current outbound policy |
| `reset bgp ipv4 external` | Hard reset all eBGP peers |
| `reset bgp ipv4 peer-group <name>` | Reset all peers in a peer group |
| `reset bgp all` | Hard reset ALL peers — use with extreme caution |

## VyOS-Specific Defaults and Behaviors

- **Timer defaults**: Keepalive 60s, holdtime 180s. Same as IOS, EOS, AOS-CX. Different from JunOS (hold 90s). Setting holdtime to 0 disables the hold-timer entirely.
- **Administrative distance**: eBGP = 20, iBGP = 200, local = 200. Same as IOS, EOS, AOS-CX, and RouterOS. Configurable with `parameters distance global`.
- **Default LOCAL_PREF**: 100. Visible as "Default local pref 100" in `show bgp ipv4 summary` header. Configurable with `parameters default local-pref`.
- **Advertisement interval default**: 0 seconds. Routes are advertised immediately when the best-path changes.
- **Network statement behavior**: BGP advertises `network` prefixes **even if the prefix is not in the routing table** (unlike IOS/EOS). To enforce routing-table presence, configure `parameters network-import-check`. Best practice: also create a static blackhole route (`set protocols static route <prefix> blackhole distance 254`) so the prefix reliably exists in the RIB.
- **RFC 8212 (`ebgp-requires-policy`) disabled by default**: Routes are advertised across eBGP without an explicit route-map/policy. Enable `parameters ebgp-requires-policy` for RFC 8212 compliance.
- **Community attribute sent by default**: Unlike some vendors, VyOS/FRR sends standard and extended communities to peers by default. Suppress with `neighbor <ip> disable-send-community standard` or `extended`.
- **Fast external failover ON by default**: eBGP sessions are immediately torn down when the directly connected interface goes down. Disable with `parameters no-fast-external-failover`.
- **Client-to-client reflection ON by default**: On route reflectors, C2C reflection is enabled. Disable with `parameters no-client-to-client-reflection` when clients are fully meshed.
- **IPv6 auto-RA active by default with extended-nexthop**: FRR sends router advertisements when using extended-nexthop or unnumbered BGP. Suppress with `parameters no-ipv6-auto-ra` — but this may break BGP unnumbered.
- **Extended-nexthop auto-enabled**: When peering over an IPv6 link-local address, `capability extended-nexthop` is automatically activated.
- **Soft reconfiguration inbound not default**: Must be explicitly configured per neighbor to enable `show bgp neighbors <ip> received-routes`.
- **commit/stage model**: All changes must be committed with `commit`. Changes are staged before activation (same as JunOS). `commit-confirm <minutes>` provides an auto-rollback safety net.
- **`maximum-prefix` terminates session**: When a neighbor exceeds its `maximum-prefix` limit, the BGP session is torn down (not just suppressed).

## Configuration Revert Patterns

VyOS uses `delete` + `commit` — there is no `no` prefix. `delete` removes a config node and all its children.

```
delete protocols bgp                                    # remove entire BGP config
delete protocols bgp neighbor <ip>                      # remove entire neighbor
delete protocols bgp neighbor <ip> remote-as            # remove (disables peer)
delete protocols bgp neighbor <ip> shutdown             # re-enable neighbor
delete protocols bgp neighbor <ip> address-family ipv4-unicast   # deactivate AF for this peer
delete protocols bgp neighbor <ip> address-family ipv4-unicast route-map   # remove both in/out route-maps
delete protocols bgp neighbor <ip> address-family ipv4-unicast prefix-list # remove prefix-lists
delete protocols bgp neighbor <ip> password             # remove authentication
delete protocols bgp neighbor <ip> ebgp-multihop        # revert to single-hop
delete protocols bgp address-family ipv4-unicast network <prefix>            # withdraw advertisement
delete protocols bgp address-family ipv4-unicast aggregate-address <prefix>  # remove aggregate
delete protocols bgp address-family ipv4-unicast redistribute <source>       # remove redistribution
delete protocols bgp address-family ipv4-unicast maximum-paths ebgp          # revert to 1 (no ECMP)
delete protocols bgp timers holdtime                    # revert to 180s
delete protocols bgp timers keepalive                   # revert to 60s
delete protocols bgp parameters router-id               # revert to highest interface IP
delete protocols bgp parameters dampening               # disable route dampening
delete protocols bgp peer-group <name>                  # remove peer group
```

After any `delete`, run `commit` to activate. Use `rollback` to revert uncommitted staged changes. Use `commit-confirm <minutes>` for a timed safety window.

**Non-obvious exceptions**:

| Scenario | Correct sequence | Gotcha |
|----------|-----------------|--------|
| Remove a neighbor | `delete protocols bgp neighbor <ip>` + `commit` | Removes ALL neighbor config at once. No granular undo. |
| Re-enable shutdown peer | `delete protocols bgp neighbor <ip> shutdown` + `commit` | `set ... shutdown` adds it; `delete ... shutdown` removes it (re-enables). |
| Revert route-map direction | `delete ... route-map` removes both import and export at once | To remove only one direction: `delete ... route-map import <name>` |
| Remove network-import-check | `delete protocols bgp parameters network-import-check` + `commit` | Reverts to advertising network statements even without a matching route. |

## Common Gotchas on VyOS

- **`show bgp ipv4` not `show ip bgp`**: VyOS uses `show bgp ipv4` (FRR-style). Automation parsers written for IOS/EOS must be adapted.
- **Network statements advertised without RIB entry by default**: Without `parameters network-import-check`, the prefix is advertised even if no matching route exists. Use a blackhole static route as a companion to every `network` statement.
- **`delete` keyword instead of `no`**: VyOS uses `delete <path>` to remove configuration. There is no `no` prefix as on IOS/EOS.
- **No explicit process start**: The BGP process starts when the first neighbor is configured. `delete protocols bgp` stops it completely.
- **`prefix-list` and `distribute-list` are mutually exclusive** per neighbor per direction. Configuring both causes a commit error.
- **`allowas-in` is eBGP-only** — cannot be applied to iBGP neighbors or peer groups.
- **`local-as` is eBGP-only** — not applicable to iBGP neighbors.
- **`ebgp-multihop` and `ttl-security` are mutually exclusive** — configuring both on the same neighbor causes a commit error.
- **Route filtering order (inbound)**: route-map → filter-list → prefix-list/distribute-list.
- **Route filtering order (outbound)**: prefix-list/distribute-list → filter-list → route-map.
- **`soft-reconfiguration inbound` required for `received-routes`**: Without it, `show bgp neighbors <ip> received-routes` returns nothing.
- **Communities sent by default**: VyOS/FRR sends communities to peers by default. Use `disable-send-community` if you want to suppress them selectively.
- **`commit-confirm` safety net**: VyOS supports `commit-confirm <minutes>` — auto-rollback if not re-confirmed. Not available on IOS/EOS — a useful safety feature for potentially disruptive BGP changes.
- **`ebgp-requires-policy` off by default**: In security-sensitive environments, enable `parameters ebgp-requires-policy` to prevent inadvertent full routing table advertisement on eBGP sessions.
- **`strict` on `local-role`**: If `strict` is set, the session will not establish if the peer does not also declare a role. Use with caution in mixed-vendor environments.
- **Listen range security**: `listen range <prefix>` keeps an open listening socket — configure firewall rules to protect the router from unauthorized BGP connection attempts.

## Key RFCs

| RFC | Title | Relevance |
|-----|-------|-----------|
| RFC 4271 | A Border Gateway Protocol 4 (BGP-4) | Core protocol specification |
| RFC 4760 | Multiprotocol Extensions for BGP-4 | Address family support |
| RFC 4456 | BGP Route Reflection | `route-reflector-client`, `cluster-id` |
| RFC 5065 | AS Confederations for BGP | `parameters confederation` |
| RFC 1997 | BGP Communities Attribute | Standard communities |
| RFC 4724 | Graceful Restart Mechanism for BGP | Graceful restart |
| RFC 7911 | Advertisement of Multiple Paths (Add-Path) | Add-path capability |
| RFC 2385 | TCP MD5 Signature for BGP Sessions | `password` authentication |
| RFC 9234 | BGP Roles (Route Leak Prevention) | `local-role`, `remote-as internal/external` |
| RFC 8212 | Default EBGP Route Propagation without Policies | `parameters ebgp-requires-policy` |
| RFC 2439 | BGP Route Flap Damping | `parameters dampening` |
| RFC 5549 | IPv4 NLRIs with IPv6 Next Hop | `capability extended-nexthop`, BGP unnumbered |
| RFC 6793 | 4-Octet AS Number Space | 4-byte ASN support |
