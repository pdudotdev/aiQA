# BGP on Arista EOS

## Configuration Syntax

```
service routing protocols model multi-agent
!
router bgp <asn>
   router-id <x.x.x.x>
   no bgp default ipv4-unicast
   bgp bestpath as-path multipath-relax
   bgp graceful-restart
   bgp graceful-restart-helper
   bgp listen range <prefix>/<len> peer-group <name> remote-as <asn>
   timers bgp <keepalive> <holdtime>
   distance bgp <external> <internal> <local>
   maximum-paths <n> [ecmp <n>]
   neighbor <ip> remote-as <asn>
   neighbor <ip> update-source <interface>
   neighbor <ip> password <key>
   neighbor <ip> description <text>
   neighbor <ip> send-community [standard | extended | large]
   neighbor <ip> peer group <name>
   neighbor <ip> shutdown
   !
   address-family ipv4
      neighbor <ip> activate
      neighbor <ip> route-map <name> {in | out}
      neighbor <ip> prefix-list <name> {in | out}
      neighbor <ip> default-originate [route-map <name>]
      network <prefix>/<len> [route-map <name>]
      redistribute <protocol> [route-map <name>]
      aggregate-address <prefix>/<len> [summary-only] [as-set] [attribute-map <name>]
!
ip community-list standard <name> permit <community>
ip community-list expanded <name> permit <regex>
```

EOS requires `service routing protocols model multi-agent` for modern BGP features (route refresh, graceful restart, add-path, dynamic peers). The legacy `ribd` model is deprecated and lacks these capabilities.

EOS uses CIDR notation (`/24`) in `network` and `aggregate-address` statements. Running-config normalizes to CIDR.

## VRF Configuration

```
router bgp <asn>
   vrf <vrf-name>
      rd <rd-value>
      route-target import <rt>
      route-target export <rt>
      router-id <x.x.x.x>
      neighbor <ip> remote-as <asn>
      neighbor <ip> update-source <interface>
      !
      address-family ipv4
         neighbor <ip> activate
         network <prefix>/<len>
         redistribute <protocol> [route-map <name>]
```

EOS uses a nested `vrf` block under `router bgp` rather than `address-family ipv4 vrf <name>` (the IOS approach). Each VRF block contains its own neighbors, address-families, and route distinguisher/route-target configuration.

VRF-aware show commands append `vrf <name>` at the end:
- `show ip bgp summary vrf <name>`
- `show ip bgp neighbor vrf <name>`
- `show ip bgp vrf <name>`

## Verification Commands

| Command | Purpose |
|---------|---------|
| `show ip bgp summary` | Peer state, ASN, prefixes received, uptime |
| `show ip bgp` | Full BGP table with best path, next-hop, metric, local-pref, AS path |
| `show ip bgp <prefix>` | All paths for a specific prefix; shows best-path selection |
| `show ip bgp <prefix> detail` | Full path detail including "Not best: \<reason\>" labels |
| `show ip bgp neighbor <ip>` | Detailed peer state: timers, capabilities, address-families, counters |
| `show ip bgp neighbor <ip> received-routes` | Routes received from peer (before inbound policy) |
| `show ip bgp neighbor <ip> advertised-routes` | Routes advertised to peer (after outbound policy) |
| `show ip bgp neighbor <ip> routes` | Routes accepted from peer (after inbound policy) |
| `show ip bgp paths` | All path entries in the BGP path table |
| `show ip bgp community <community>` | Routes matching a specific community value |
| `show ip bgp regexp <as-path-regex>` | Routes matching an AS path regular expression |
| `show ip bgp detail` | Extended detail per prefix: community, originator, cluster-list |
| `show bgp convergence` | BGP convergence state, pending peers, timers |
| `show bgp update-group` | Update group membership and policy statistics |
| `show running-config section bgp` | Current BGP configuration |

**`show ip bgp` status codes**:
```
s suppressed  * valid  > best  # not installed in RIB  E ECMP-head  e ECMP-contributor
S Stale  c ECMP-contributor  b backup  % pending convergence
Origin: i IGP  e EGP  ? incomplete
```

## EOS-Specific Defaults and Behaviors

- **Router ID selection**: (1) explicit `router-id` under `router bgp`, (2) highest loopback IP, (3) highest interface IP. Always set manually.
- **Timer defaults**: Keepalive 60s, Hold time 180s. Configurable with `timers bgp <keepalive> <holdtime>`.
- **Default LOCAL_PREF**: 100. Applied to iBGP-learned and locally originated routes.
- **Maximum-paths default**: 1 (no ECMP). `maximum-paths <n>` enables multipath; `bgp bestpath as-path multipath-relax` is **enabled by default** (unlike most vendors) — paths with different AS path content but same length are treated as equal-cost.
- **Administrative distance**: eBGP 200, iBGP 200, local 200. **Major cross-vendor difference**: EOS defaults to 200 for ALL BGP routes including eBGP (IOS uses 20 for eBGP). Configure `distance bgp 20 200 200` explicitly to match IOS behavior.
- **`ip routing` prerequisite**: Must be enabled globally. BGP will not install routes or form TCP sessions without it.
- **Multi-agent vs ribd**: `service routing protocols model multi-agent` required for route refresh, graceful restart, add-path, dynamic peers, BGP unnumbered. Changing the routing model requires a reboot.
- **Neighbor activation**: Neighbors are NOT automatically activated in any address-family. Use `no bgp default ipv4-unicast` (recommended) and explicitly activate with `neighbor <ip> activate` under `address-family ipv4`.
- **Send-community**: Not sent by default. Must configure `neighbor <ip> send-community`.
- **`bgp advertise-inactive`**: Disabled by default. BGP routes that are not the best path in the RIB (e.g., OSPF is preferred) are not advertised to peers. Enable `bgp advertise-inactive` to advertise them anyway.
- **`bgp log-neighbor-changes`**: Enabled by default. Logs BGP peer state transitions.
- **Single BGP instance per VRF**: Only one `router bgp <asn>` per VRF. Attempting a second ASN in the same VRF will fail.
- **Graceful restart**: `bgp graceful-restart` (restarting speaker) and `bgp graceful-restart-helper` (helper mode) both require multi-agent mode.
- **Section filter**: EOS uses `section` keyword directly (no pipe): `show running-config section bgp`.

## Configuration Revert Patterns

**General rule**: Prefix any command with `no` to remove it. `default <command>` explicitly resets to factory default. Changes take effect immediately.

```
no neighbor <ip>                          # removes entire neighbor config
no neighbor <ip> remote-as                # removes remote-as (effectively disables peer)
no neighbor <ip> password                 # removes MD5 authentication
no neighbor <ip> route-map <name> in      # removes inbound route-map
no neighbor <ip> prefix-list <name> in    # removes inbound prefix-list
no neighbor <ip> default-originate        # stops advertising default route to peer
no neighbor <ip> send-community           # stops sending communities
no network <prefix>/<len>                 # removes network advertisement
no redistribute <protocol>                # removes redistribution
no aggregate-address <prefix>/<len>       # removes aggregate
no maximum-paths                          # reverts to 1
no timers bgp                             # reverts to 60/180
no distance bgp                           # reverts to 200/200/200
```

**`default` keyword** (EOS-specific): `default neighbor <ip> send-community` resets to factory default rather than just negating.

**Session reset commands**:

| Command | Effect |
|---------|--------|
| `clear ip bgp <ip>` | Hard reset — tears down TCP session, full re-exchange |
| `clear ip bgp <ip> soft in` | Soft inbound reset — re-applies inbound policy without dropping session |
| `clear ip bgp <ip> soft out` | Soft outbound reset — re-sends routes with current outbound policy |
| `clear ip bgp counters [<ip>]` | Reset message/statistics counters without resetting sessions |
| `clear ip bgp errors [<ip>]` | Reset error statistics for peers |
| `clear ip bgp *` | Hard reset ALL peers — use with extreme caution |

Some configuration changes require a session reset to take effect: weight changes, distribution list changes, timers, and administrative distance (hard reset required for AD changes).

## Common Gotchas on EOS

- **eBGP AD is 200 by default** (not 20 like IOS). eBGP routes have the same preference as iBGP, causing unexpected route selection in mixed-vendor networks. Configure `distance bgp 20 200 200` to match IOS behavior.
- **Multi-agent mode required**: Many features (graceful restart, route refresh, add-path, dynamic peers) silently fail or are unavailable under `ribd`. Always verify `service routing protocols model multi-agent`. Changing the routing model requires a reboot.
- **`ip routing` prerequisite**: BGP will not form TCP sessions or install routes without `ip routing` enabled globally.
- **VRF syntax differs from IOS**: EOS uses a nested `vrf` block; IOS uses `address-family ipv4 vrf <name>`. Copying IOS config directly to EOS will fail.
- **Neighbors not activated by default**: Peers establish TCP but exchange no prefixes unless `neighbor <ip> activate` is configured under `address-family ipv4`.
- **Send-community not on by default**: Community-based policies silently fail if `neighbor <ip> send-community` is missing.
- **`no bgp default ipv4-unicast`**: Without it, all configured neighbors are auto-activated in IPv4 unicast, which may cause unintended route exchange.
- **`bgp bestpath as-path multipath-relax` is ON by default**: Paths with different AS path content but same length are equal-cost. Use `no bgp bestpath as-path multipath-relax` to require identical AS paths for ECMP.
- **`bgp enforce-first-as` is ON by default**: eBGP routes where the first AS doesn't match `remote-as` are discarded. Disable with `no bgp enforce-first-as` or `no neighbor <ip> enforce-first-as`.
- **VRF must be specified in show commands**: `show ip bgp summary` without VRF shows only default VRF.

## Best-Path Selection

EOS BGP best-path selection follows this ordered sequence (first differing criterion wins):

1. Path weight (highest) — EOS-local, not advertised, default 0
2. LOCAL_PREF (highest) — default 100
3. Locally originated (local static, network, or aggregate preferred over learned)
4. AS path length (shortest) — disable with `bgp bestpath as-path ignore`
5. Origin code (IGP < EGP < Incomplete)
6. MED (lowest) — compared only within same AS by default; `bgp always-compare-med` enables cross-AS; missing MED = 0 (best) unless `bgp bestpath med missing-as-worst`
7. eBGP over iBGP
8. IGP metric to next-hop (lowest)
9. AS path details (when `no bgp bestpath as-path multipath-relax`, paths with different AS path content are unequal)
10. Tie-break: router ID (lowest), optionally CLUSTER_LIST length or router ID tiebreakers, then peer IP, then path ID

To see why a path was not selected: `show ip bgp <prefix> detail` — non-best paths show a "Not best: \<reason\>" label (e.g., "path weight", "local preference", "AS path length", "IGP cost", "router ID", "peer IP address").

## Best-Path Selection Configuration

```
bgp always-compare-med               # compare MED across different ASes (disabled by default)
bgp bestpath as-path ignore          # ignore AS path length in selection (disabled by default)
no bgp bestpath as-path multipath-relax  # disable multipath-relax (it is ON by default)
bgp bestpath ecmp-fast               # prefer first-received in ECMP tie (default)
no bgp bestpath ecmp-fast            # ignore arrival order in ECMP group evaluation
bgp bestpath med confed              # compare MED for confederation routes (disabled by default)
bgp bestpath med missing-as-worst    # treat missing MED as highest (least preferred) value
bgp bestpath tie-break cluster-list-length  # prefer shortest CLUSTER_LIST at step 10
bgp bestpath tie-break router-id     # prefer lowest ROUTER_ID at step 10
bgp advertise-inactive               # advertise BGP routes even when not best in RIB
bgp enforce-first-as                 # enforce first AS in path matches remote-as (on by default)
```

## Neighbor-Level Configuration (Extended)

```
neighbor <ip> ebgp-multihop [<ttl>]       # allow eBGP session over multiple hops (default: single hop)
neighbor <ip> next-hop-self               # force this router as next-hop for iBGP peers
neighbor <ip> next-hop-peer               # use peer address as next-hop
neighbor <ip> remove-private-as           # strip private ASNs from outbound AS path
neighbor <ip> allowas-in                  # accept routes containing local ASN in path
neighbor <ip> maximum-routes <n>          # limit prefixes accepted from peer
neighbor <ip> weight <value>              # set local weight for routes from peer (default 0, highest wins)
neighbor <ip> passive                     # do not initiate TCP connection to peer
neighbor <ip> route-reflector-client      # designate neighbor as route reflector client
neighbor <ip> graceful-restart            # per-neighbor graceful restart
neighbor <ip> graceful-restart-helper     # per-neighbor helper mode
```

## Peer Groups

EOS supports both static and dynamic peer groups.

**Static peer groups** consolidate configuration for multiple neighbors:

```
neighbor <name> peer group              # create static peer group
neighbor <ip> peer group <name>         # assign neighbor to peer group
```

All `neighbor` commands can be applied to peer groups. Individual neighbor overrides take precedence.

**Dynamic peer groups** (listen range) accept connections from any peer in a subnet:

```
bgp listen range <prefix>/<len> peer-group <name> remote-as <asn>
bgp listen range <prefix>/<len> peer-group <name> peer-filter <filter-name>
```

`peer-filter` allows accepting peers from a range of AS numbers. `dynamic peer max <n>` limits total dynamic peers. Requires multi-agent mode.

```
show ip bgp peer-group [<name>]     # peer group configuration and members
show peer-filter [<name>]           # peer filter configuration
```

## Route Reflection

```
neighbor <ip> route-reflector-client              # designate neighbor as RR client
bgp cluster-id <id>                               # set cluster ID (required with multiple RRs in cluster)
no bgp client-to-client reflection                # disable C2C reflection when clients are fully meshed
bgp route-reflector preserve-attributes [always]  # preserve next-hop/localpref/metric on reflected routes
```

Cluster ID defaults to the router ID when only one RR exists. Multiple RRs in a cluster must share the same explicit `bgp cluster-id`. The `always` keyword on `preserve-attributes` overrides even outbound route-map modifications.

## BGP Confederations

```
bgp confederation identifier <as-number>    # set the confederation's external AS number
bgp confederation peers <as-range>          # define which sub-ASes are in the confederation
```

Sub-ASes use eBGP between each other but exchange iBGP attributes. External peers see only the confederation identifier.

## BGP Graceful Restart

```
bgp graceful-restart                     # enable as restarting speaker (globally)
bgp graceful-restart-helper             # enable helper mode (globally)
neighbor <ip> graceful-restart          # per-neighbor graceful restart
neighbor <ip> graceful-restart-helper   # per-neighbor helper mode
graceful-restart stalepath-time <n>     # how long helper preserves stale routes (default: 300s)
```

Both require multi-agent mode. During restart, routes from the restarting peer are marked Stale (`S` in `show ip bgp`). The helper maintains forwarding using stale routes until the restarting speaker sends EOR or the stalepath timer expires.

## BGP Convergence

Prevents FIB churn during reload by holding route advertisements until all peers have rejoined and sent their routes.

```
update wait-for-convergence                  # enable BGP convergence feature
bgp convergence time <1-3600>               # max wait time (default: 300s)
bgp convergence slow-peer time <1-3600>     # timeout for slow peers to establish (default: 90s)
show bgp convergence                        # convergence state, pending peers, timers
```

Routes pending convergence show `%` status code in `show ip bgp`.

## BGP Additional Paths Send (Add-Path TX)

EOS supports advertising multiple paths for the same prefix to a peer (RFC 7911). Configuration at three levels:

```
# Global level:
bgp additional-paths send {any|ecmp|backup|limit <n>}

# Address-family level:
address-family ipv4
   bgp additional-paths send {any|ecmp|backup|limit <n>}

# Per-neighbor level:
neighbor <ip> additional-paths send {any|ecmp|backup|limit <n>}
```

Send modes: `any` = all paths, `ecmp` = all ECMP paths, `backup` = best + backup paths, `limit <n>` = at most n paths. Requires multi-agent mode and Add-Path receive capability on the peer.

## BGP Aggregate Address (Extended)

```
aggregate-address <prefix>/<len> [as-set] [summary-only] [attribute-map <name>] [match-map <name>]
```

- `as-set`: includes AS_SET with AS numbers from contributing routes; without it, ATOMIC_AGGREGATE is set
- `summary-only`: suppresses more-specific contributor routes
- `attribute-map <name>`: applies route-map set commands to the aggregate route's attributes
- `match-map <name>`: filters which contributors are included (requires `summary-only`)

Aggregate routes become active if any contributor exists (including static routes). Aggregate routes are automatically redistributed and this cannot be disabled.

## BGP Aggregate Minimum Contributors

```
aggregate-address <prefix>/<len> minimum-contributors <1-65535>
```

EOS will not generate the aggregate unless at least this many active contributor subnets exist. Prevents blackholing when too few component routes are present. Default is 1.

## BGP Shutdown Command

```
shutdown          # disable BGP without removing configuration
no shutdown       # re-enable BGP
```

`shutdown` under `router bgp` disables BGP operations but preserves configuration. Distinct from `no router bgp <asn>` which removes all configuration.

## Key RFCs

| RFC | Title | Relevance |
|-----|-------|-----------|
| RFC 4271 | A Border Gateway Protocol 4 (BGP-4) | Core BGP specification: FSM, UPDATE format, path attributes, decision process |
| RFC 4893 | BGP Support for Four-Octet AS Number Space | 4-byte ASN support (AS_TRANS, NEW_AS_PATH) |
| RFC 4456 | BGP Route Reflection | Route reflector clusters, ORIGINATOR_ID, CLUSTER_LIST |
| RFC 5065 | Autonomous System Confederations for BGP | Sub-AS design for iBGP scaling |
| RFC 4760 | Multiprotocol Extensions for BGP-4 | MP_REACH_NLRI / MP_UNREACH_NLRI for IPv6, VPNv4, EVPN |
| RFC 1997 | BGP Communities Attribute | Standard community values (NO_EXPORT, NO_ADVERTISE, etc.) |
| RFC 8092 | BGP Large Communities Attribute | Large communities (4-byte ASN compatible) |
| RFC 4724 | Graceful Restart Mechanism for BGP | Graceful restart capability negotiation and procedures |
| RFC 7911 | Advertisement of Multiple Paths in BGP (Add-Path) | Add-Path send/receive for path diversity |
| RFC 2385 | Protection of BGP Sessions via the TCP MD5 Signature Option | MD5 authentication for BGP TCP sessions |
| RFC 5291 | Outbound Route Filtering Capability for BGP-4 | ORF for delegating filtering to the sending peer |
| RFC 7947 | Internet Exchange BGP Route Server | Route server operations at IXPs |
