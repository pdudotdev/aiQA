# BGP on Cisco IOS / IOS-XE

## Configuration Syntax

```
router bgp <asn>
 bgp router-id <x.x.x.x>
 bgp log-neighbor-changes
 bgp graceful-restart
 bgp bestpath as-path multipath-relax
 bgp bestpath med missing-as-worst
 bgp asnotation dot                              ! enable asdot notation for 4-byte ASN
 timers bgp <keepalive> <holdtime>               ! process-wide BGP timers
 maximum-paths <count>                           ! ECMP paths (default 1)
 neighbor <ip> remote-as <asn>
 neighbor <ip> description <text>
 neighbor <ip> update-source <interface>
 neighbor <ip> ebgp-multihop <ttl>
 neighbor <ip> password <key>
 neighbor <ip> timers <keepalive> <holdtime>     ! per-neighbor override
 neighbor <ip> advertisement-interval <seconds>  ! min interval between updates (default: 30s iBGP, 0s eBGP)
 neighbor <ip> shutdown                          ! admin-disable without removing config
 !
 address-family ipv4 unicast
  network <prefix> mask <mask>
  redistribute <protocol> [route-map <name>]
  neighbor <ip> activate
  neighbor <ip> next-hop-self
  neighbor <ip> route-map <name> {in | out}
  neighbor <ip> prefix-list <name> {in | out}
  neighbor <ip> soft-reconfiguration inbound
  neighbor <ip> default-originate [route-map <name>]
  neighbor <ip> send-community [both | standard | extended]
  neighbor <ip> maximum-prefix <max> [<threshold>%] [restart <minutes>] [warning-only]
  neighbor <ip> unsuppress-map <name>
  aggregate-address <prefix> <mask> [summary-only] [as-set] [suppress-map <name>]
 exit-address-family
!
ip community-list {standard | expanded} <name> {permit | deny} <community>
ip prefix-list <name> seq <n> {permit | deny} <prefix>/<len> [ge <n>] [le <n>]
!
route-map <name> {permit | deny} <seq>
 match community <list-name>
 match ip address prefix-list <name>
 set community <community> [additive]
 set local-preference <value>
 set as-path prepend <asn> [<asn> ...]
 set metric <value>
```

IOS/IOS-XE uses `address-family ipv4 unicast` to activate neighbors and apply per-AFI policies. Neighbors must be explicitly activated with `neighbor <ip> activate` inside the address-family. The neighbor definition (`remote-as`, `update-source`, `password`, `ebgp-multihop`) is configured in router-level scope, while route policies, activation, and prefix advertisement are configured inside the address-family.

## VRF Configuration

```
router bgp <asn>
 address-family ipv4 vrf <vrf-name>
  rd <asn:nn | ip:nn>
  route-target import <rt>
  route-target export <rt>
  neighbor <ip> remote-as <asn>
  neighbor <ip> activate
  network <prefix> mask <mask>
 exit-address-family
```

VRF neighbors are defined and activated entirely within the `address-family ipv4 vrf` block. The `rd` and `route-target` statements control VPNv4 route distinguisher and import/export policy. VRF-aware show commands append `vrf <name>`:
- `show ip bgp vpnv4 vrf <name>`
- `show ip bgp vpnv4 vrf <name> summary`
- `show ip bgp vpnv4 vrf <name> neighbors`

## Verification Commands

| Command | Purpose |
|---------|---------|
| `show ip bgp summary` | Neighbor count, ASN, state/prefix count, up/down time, router-id |
| `show ip bgp` | Full BGP table with best path, next-hop, metric, local-pref, weight |
| `show ip bgp <network> <mask>` | Detail for a specific prefix: all paths, attributes, best-path selection |
| `show ip bgp neighbor <ip>` | Detailed neighbor state: timers, capabilities, AFI/SAFI, messages |
| `show ip bgp neighbor <ip> routes` | Routes accepted from neighbor and installed in BGP table (no soft-reconfig needed) |
| `show ip bgp neighbor <ip> received-routes` | All routes received from neighbor before inbound policy (requires `soft-reconfiguration inbound`) |
| `show ip bgp neighbor <ip> advertised-routes` | Routes advertised to neighbor after outbound policy |
| `show ip bgp paths` | All BGP path attributes in the database (verifies AS-path and attribute propagation) |
| `show ip bgp rib-failure` | BGP routes NOT installed in the RIB — present in BGP table but overridden by a lower-AD route |
| `show ip bgp community <community>` | Routes matching a specific community value |
| `show ip bgp regexp <as-path-regex>` | Routes matching an AS-path regular expression |
| `show ip bgp prefix-list <name>` | Routes matching a prefix-list filter |
| `show running-config \| section bgp` | Current BGP configuration |

**`show ip bgp` status codes** (required for writing specific assertions):

```
Status codes: s suppressed, d damped, h history, * valid, > best, i - internal,
              r RIB-failure, S Stale
Origin codes: i - IGP, e - EGP, ? - incomplete
```

Key codes: `*` = valid route (next-hop reachable), `>` = best path selected, `i` = learned via iBGP, `r` = valid but not installed in RIB (another protocol has lower AD), `s` = suppressed by aggregate. Locally originated routes show next-hop `0.0.0.0` and weight `32768`.

## IOS-Specific Defaults and Behaviors

- **Timer defaults**: Hold time 180s, keepalive 60s. Negotiated to the lower value between peers. Configurable globally with `timers bgp <keepalive> <holdtime>` or per-neighbor with `neighbor <ip> timers`.

- **LOCAL_PREF default**: 100. Applied to iBGP-learned and locally originated routes. Not carried in eBGP updates. Configurable via route-map `set local-preference`.

- **MED default**: 0. Missing MED treated as 0 unless `bgp bestpath med missing-as-worst` is configured, which treats missing MED as 4294967295. MED comparison only between paths from the same neighboring AS unless `bgp always-compare-med` is set.

- **BGP scanner interval**: 60 seconds. Periodically walks the BGP table to validate next-hop reachability and trigger best-path recalculation.

- **Administrative distance**: eBGP = 20, iBGP = 200, locally originated = 200. eBGP routes preferred over any IGP (OSPF 110, EIGRP 90). Configurable with `distance bgp <ebgp> <ibgp> <local>`.

- **Neighbor activation**: By default, IOS/IOS-XE **auto-activates** neighbors in the IPv4 unicast address-family when `neighbor <ip> remote-as` is configured. The exception: if `no bgp default ipv4-unicast` is configured **before** the neighbor statement, auto-activation is suppressed and `neighbor <ip> activate` must be explicit. `no bgp default ipv4-unicast` has no effect on existing neighbors — only on neighbors added after it.

- **bgp log-neighbor-changes**: Enabled by default on IOS-XE. Logs neighbor state transitions (Idle, Connect, Active, OpenSent, OpenConfirm, Established). On classic IOS, must be explicitly enabled.

- **Maximum-paths default**: 1. No ECMP without explicit `maximum-paths <n>` config. For eBGP multipath, `bgp bestpath as-path multipath-relax` allows paths from different ASNs to be considered equal-cost.

- **Best path selection order**: Weight (Cisco-proprietary, highest wins) > LOCAL_PREF (highest) > locally originated > AS-path length (shortest) > origin type (IGP < EGP < incomplete) > MED (lowest) > eBGP over iBGP > IGP metric to next-hop (lowest) > oldest route > lowest router-id > lowest neighbor address. Weight and locally-originated preference are Cisco-specific additions beyond RFC 4271.

- **Weight for locally originated routes**: Routes introduced via `network` or `aggregate-address` have a default weight of **32768**. Routes learned from peers have weight 0. This is why locally originated routes win over any learned route before LOCAL_PREF is even considered.

- **`bgp fast-external-fallover`**: Enabled by default on IOS/IOS-XE. When the directly connected interface to an eBGP peer goes down, the session is immediately torn down without waiting for the hold-timer to expire. Disable with `no bgp fast-external-fallover` when peering over shared media where interface up/down does not indicate peer reachability.

- **`bgp router-id` change resets all sessions**: Configuring or changing `bgp router-id` forces a reset of **all** active BGP sessions. Plan router-id changes during maintenance windows.

- **`neighbor shutdown`**: Administratively disables a neighbor without removing its configuration (route-maps, timers, prefix-lists all preserved). Preferred for maintenance over `no neighbor <ip>` which destroys all config. Re-enable with `no neighbor <ip> shutdown`.

- **`neighbor maximum-prefix`**: `neighbor <ip> maximum-prefix <max> [<threshold>%] [restart <minutes>] [warning-only]` — terminates the session when the peer exceeds `<max>` prefixes. With `warning-only`, logs a warning but does not terminate. With `restart`, the session auto-recovers after the specified interval. `threshold` (percentage) sets an early warning level.

- **`bgp soft-reconfig-backup`**: Process-level alternative to per-neighbor `soft-reconfiguration inbound`. Applies inbound soft-reconfig **only for peers that do not support route-refresh** (RFC 2918). Peers supporting route-refresh are unaffected. Preferable to enabling soft-reconfig on every neighbor since it stores updates only when necessary.

- **Soft reconfiguration inbound**: `neighbor <ip> soft-reconfiguration inbound` stores a copy of all received routes before inbound policy is applied. Required to use `show ip bgp neighbor <ip> received-routes`. Increases memory usage; route-refresh capability (RFC 2918) is preferred when supported.

- **4-byte ASN support**: Enabled by default. Plain notation (e.g., 65536) is the default. `bgp asnotation dot` switches to asdot notation (e.g., 1.0). Change requires `clear ip bgp *` to take effect.

- **Auto-summary**: Disabled by default on modern IOS (12.3+) and IOS-XE. When enabled, BGP `network` statements auto-summarize to classful boundaries.

- **Synchronization**: Disabled by default on modern IOS (12.2(8)T+) and IOS-XE. When enabled, BGP will not advertise a route learned via iBGP unless the same route exists in the IGP table.

- **Graceful restart**: `bgp graceful-restart` enables RFC 4724 graceful restart. Helper mode is enabled by default. Restart time default is 120 seconds, stalepath time default is 360 seconds.

## Configuration Revert Patterns

**General rule**: Prefix any command with `no` to remove it. BGP configuration changes take effect immediately with no commit step. Removing a neighbor deletes all configuration associated with that neighbor (route-maps, filters, timers, password).

```
no neighbor <ip>                       # removes neighbor and ALL associated config
no neighbor <ip> route-map <name> in   # removes only the inbound route-map
no network <prefix> mask <mask>        # withdraws the network advertisement
no redistribute <protocol>             # removes redistribution
no route-map <name>                    # removes entire route-map
no ip community-list <name>            # removes community list
no ip prefix-list <name>               # removes prefix list
default neighbor <ip>                  # resets all neighbor config to defaults
clear ip bgp * soft                    # soft reconfiguration (no session drop)
clear ip bgp * soft in                 # soft reconfiguration inbound only
clear ip bgp * soft out                # soft reconfiguration outbound only
clear ip bgp *                         # hard reset — drops ALL BGP sessions
clear ip bgp <ip>                      # hard reset — drops single neighbor session
```

**Non-obvious exceptions**:

| Scenario | Correct sequence | Gotcha |
|----------|-----------------|--------|
| Remove a single neighbor | `no neighbor <ip>` | Removes ALL config for that neighbor — route-maps, prefix-lists, timers, password, description. There is no undo. Re-add requires full reconfiguration. |
| Change neighbor ASN | `no neighbor <ip> remote-as <old-asn>` then `neighbor <ip> remote-as <new-asn>` | Changing `remote-as` removes ALL associated neighbor config (same as full removal). Must reconfigure route-maps, filters, and timers. |
| Reset after policy change | `clear ip bgp <ip> soft in` (inbound) or `clear ip bgp <ip> soft out` (outbound) | `clear ip bgp *` (hard reset) drops all sessions and causes route withdrawal. Always prefer soft reset. |
| Revert address-family config | `no address-family ipv4 vrf <name>` | Removes entire AF block including all VRF neighbors and networks. Cannot undo individual items inside a deleted AF. |

## Common Gotchas on IOS

- Forgetting `neighbor <ip> activate` in address-family — the neighbor comes up (Established) but exchanges no prefixes. The session is up, the BGP table is empty. This is the most common BGP misconfiguration on IOS-XE.
- iBGP next-hop unreachable — eBGP-learned routes advertised to iBGP peers retain the original eBGP next-hop by default. If the iBGP peer has no route to that next-hop, the route is marked as invalid. Fix with `neighbor <ip> next-hop-self` on the eBGP border router, or ensure the IGP carries the eBGP next-hop subnet.
- Route-map applied to wrong direction (`in` vs `out`) — `neighbor <ip> route-map <name> in` filters received routes; `out` filters advertised routes. Swapping them silently applies the wrong policy with no error.
- Missing `subnets` keyword on `redistribute` — without it, only classful network boundaries are redistributed. This gotcha is identical to the OSPF redistribution behavior.
- BGP split horizon — routes learned from an iBGP peer are not re-advertised to other iBGP peers. Requires either a full mesh of iBGP sessions, route reflectors (`neighbor <ip> route-reflector-client`), or confederations. This is RFC 4271 behavior, not a bug.
- `no neighbor <ip>` removes ALL associated config — route-maps, prefix-lists, timers, password, and description are all deleted when the neighbor statement is removed. Use `no neighbor <ip> route-map <name> in` to remove individual attributes without destroying the entire neighbor config.
- Weight is Cisco-proprietary and overrides all other path selection attributes — a neighbor with `neighbor <ip> weight 100` will always be preferred over LOCAL_PREF, AS-path, or MED. Weight is not advertised to peers; it is local only.
- Locally originated routes (via `network` or `aggregate-address`) have a default weight of **32768**; all peer-learned routes have weight 0. This makes locally originated routes always win in the weight step before any other attribute is compared.
- `bgp fast-external-fallover` is enabled by default — eBGP sessions are immediately torn down when the directly connected interface goes down. On shared-media networks where interface state does not reflect peer reachability, this can cause flapping.
- Changing `bgp router-id` resets ALL active BGP sessions. This is not gradual — all peers see a session reset simultaneously.
- `clear ip bgp *` drops ALL sessions — causes a full convergence event. Always use `clear ip bgp * soft` or `clear ip bgp <ip> soft in/out` for policy changes.
- `bgp asnotation dot` changes both the display format AND the pattern-matching format for `show ip bgp regexp`. When dot notation is active, regular expressions must use asdot notation (e.g., `^1\.0$` instead of `^65536$`) or matches silently return no results.

## Key RFCs

- **RFC 4271** — A Border Gateway Protocol 4 (BGP-4). Core protocol specification: finite state machine, UPDATE message format, path attributes, decision process.
- **RFC 4760** — Multiprotocol Extensions for BGP-4. Defines MP_REACH_NLRI and MP_UNREACH_NLRI attributes for carrying non-IPv4 address families (IPv6, VPNv4, VPNv6).
- **RFC 4724** — Graceful Restart Mechanism for BGP. Allows a BGP speaker to preserve forwarding state during restart while neighbors maintain routes.
- **RFC 2918** — Route Refresh Capability for BGP-4. Enables a BGP speaker to request re-advertisement of routes without resetting the session.
- **RFC 1997** — BGP Communities Attribute. Defines the community path attribute for route tagging and policy application.
- **RFC 4360** — BGP Extended Communities Attribute. Defines extended community values used for route-target in VPN configurations.
- **RFC 6793** — BGP Support for Four-Octet Autonomous System (AS) Number Space. Extends ASN from 2-byte to 4-byte.
- **RFC 7911** — Advertisement of Multiple Paths in BGP (ADD-PATH). Allows a BGP speaker to advertise multiple paths for the same prefix.
- **RFC 4893** — BGP Support for Four-Octet AS Number Space (transition mechanism). Defines AS 23456 (AS_TRANS) as a reserved placeholder for 4-byte ASNs in 2-byte-only UPDATE messages.
- **RFC 5396** — Textual Representation of Autonomous System (AS) Numbers. Documents asplain (default, e.g. 65536) and asdot (e.g. 1.0) notation formats. Relevant to `bgp asnotation dot`.
