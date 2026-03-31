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

EOS uses a nested `vrf` block under `router bgp` rather than `address-family ipv4 vrf <name>` (the IOS approach). This is a key syntax difference. Each VRF block contains its own neighbors, address-families, and route distinguisher/route-target configuration.

VRF-aware show commands append `vrf <name>` at the end:
- `show ip bgp summary vrf <name>`
- `show ip bgp neighbor vrf <name>`
- `show ip bgp vrf <name>`

## Verification Commands

| Command | Purpose |
|---------|---------|
| `show ip bgp summary` | Peer state, ASN, prefixes received, uptime |
| `show ip bgp` | Full BGP table with best path, next-hop, metric, local-pref, AS path |
| `show ip bgp neighbor <ip>` | Detailed peer state: timers, capabilities, address-families, counters |
| `show ip bgp neighbor <ip> received-routes` | Routes received from peer (before inbound policy) |
| `show ip bgp neighbor <ip> advertised-routes` | Routes advertised to peer (after outbound policy) |
| `show ip bgp neighbor <ip> routes` | Routes accepted from peer (after inbound policy) |
| `show ip bgp community <community>` | Routes matching a specific community value |
| `show ip bgp regexp <as-path-regex>` | Routes matching an AS path regular expression |
| `show ip bgp detail` | Extended detail per prefix: community, originator, cluster-list |
| `show running-config section bgp` | Current BGP configuration |

## EOS-Specific Defaults and Behaviors

- **Router ID selection**: (1) explicit `router-id` command under `router bgp`, (2) highest loopback IP, (3) highest interface IP. Always set `router-id` manually to avoid unexpected changes when interfaces go down.

- **Timer defaults**: Keepalive 60s, Hold time 180s (same as IOS). Configurable with `timers bgp <keepalive> <holdtime>`. Hold time is negotiated to the lower value between peers.
- **Default LOCAL_PREF**: 100 for iBGP-learned routes. Locally originated routes also carry LOCAL_PREF 100.
- **Maximum-paths default**: 1 (no ECMP by default). `maximum-paths <n>` enables multipath; `ecmp <n>` extends ECMP beyond the base multipath count. `bgp bestpath as-path multipath-relax` is required for multipath across different neighboring ASNs.

- **Administrative distance**: eBGP 200, iBGP 200, local 200. **This is a major cross-vendor difference**: EOS defaults to 200 for ALL BGP routes including eBGP, whereas IOS uses 20 for eBGP, 200 for iBGP, and 200 for local. To match IOS behavior, configure `distance bgp 20 200 200` explicitly.
- **Auto-summary**: Off by default. EOS does not perform automatic summarization to classful boundaries.

- **ip routing prerequisite**: `ip routing` must be enabled globally. BGP will not install routes into the RIB or form TCP sessions without it.
- **Multi-agent vs ribd**: `service routing protocols model multi-agent` runs each protocol as a separate process communicating via Sysdb. Required for: route refresh, graceful restart, add-path, dynamic peers, BGP unnumbered, and many other modern features. The legacy `ribd` model runs all protocols in a single process with limited feature support.

- **Dynamic peers**: `bgp listen range <prefix>/<len> peer-group <name> remote-as <asn>` accepts BGP sessions from any peer in the specified range without explicit neighbor statements. Requires multi-agent mode.
- **Neighbor activation**: Neighbors are NOT automatically activated in any address-family. Use `no bgp default ipv4-unicast` (recommended) or explicitly activate each neighbor under `address-family ipv4` with `neighbor <ip> activate`.
- **Send-community**: Not sent by default. Must configure `neighbor <ip> send-community` to propagate standard, extended, or large communities.

- **Graceful restart**: `bgp graceful-restart` enables graceful restart as a restarting speaker. `bgp graceful-restart-helper` enables helper mode (maintains routes from a restarting peer). Both require multi-agent mode.
- **Section filter**: EOS uses `section` keyword directly (no pipe): `show running-config section bgp`.

## Configuration Revert Patterns

**General rule**: Prefix any command with `no` to remove it. Alternatively, `default <command>` explicitly resets to factory default. Changes take effect immediately.

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

**`default` keyword alternative** (EOS-specific):

`default neighbor <ip> send-community` — resets to factory default rather than just negating. Prefer `default` when you want to be explicit about returning to the vendor default.

**Session reset commands**:

| Command | Effect |
|---------|--------|
| `clear ip bgp <ip>` | Hard reset — tears down TCP session, full re-exchange |
| `clear ip bgp <ip> soft in` | Soft inbound reset — re-applies inbound policy without dropping session |
| `clear ip bgp <ip> soft out` | Soft outbound reset — re-sends routes with current outbound policy |
| `clear ip bgp *` | Hard reset ALL peers — use with extreme caution |

## Common Gotchas on EOS

- **eBGP AD is 200 by default** (not 20 like IOS). This means eBGP routes have the same preference as iBGP routes, which can cause unexpected route selection in mixed-vendor networks. Configure `distance bgp 20 200 200` under `router bgp` to match IOS behavior.
- **Multi-agent mode required**: Many modern BGP features (graceful restart, route refresh, add-path, dynamic peers, BGP unnumbered) silently fail or are unavailable under the legacy `ribd` model. Always verify `service routing protocols model multi-agent` is configured. Changing the routing model requires a reboot.
- **`ip routing` prerequisite**: BGP will not form TCP sessions or install routes without `ip routing` enabled globally. The error is not always obvious in logs.
- **VRF syntax differs from IOS**: EOS uses a nested `vrf` block under `router bgp` with its own neighbors and address-families. IOS uses `address-family ipv4 vrf <name>`. Copying IOS config directly to EOS will fail.
- **Neighbors not activated by default**: Unlike some platforms, EOS does not automatically activate neighbors in the IPv4 unicast address-family. Peers will establish TCP but exchange no prefixes unless `neighbor <ip> activate` is configured under `address-family ipv4`.
- **Send-community not on by default**: Communities are not sent to peers unless explicitly configured with `neighbor <ip> send-community`. Policies relying on community-based filtering will silently fail if this is missing.
- **`no bgp default ipv4-unicast`**: Best practice on EOS. Without it, all configured neighbors are auto-activated in IPv4 unicast, which may cause unintended route exchange with peers intended for other address-families only.
- VRF must be specified in show commands to see VRF-specific BGP data — `show ip bgp summary` without VRF shows only default VRF.

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
