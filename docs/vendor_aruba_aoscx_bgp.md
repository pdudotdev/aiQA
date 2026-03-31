# BGP on Aruba AOS-CX

## Configuration Syntax

```
router bgp <asn>
    bgp router-id <x.x.x.x>
    neighbor <ip> remote-as <asn>
    neighbor <ip> update-source <interface>
    neighbor <ip> ebgp-multihop <ttl>
    neighbor <ip> password <key>
    neighbor <ip> timers <keepalive> <holdtime>
    neighbor <ip> timers connect-retry <seconds>
    neighbor <ip> advertisement-interval <seconds>
    neighbor <ip> route-map <name> {in | out}
    neighbor <ip> prefix-list <name> {in | out}
    neighbor <ip> shutdown
    neighbor <ip> description <text>
    neighbor <ip> next-hop-self
    neighbor <ip> route-reflector-client
    neighbor <ip> send-community {standard | extended | both}
    neighbor <ip> remove-private-AS
    neighbor <ip> allowas-in [<count>]
    neighbor <ip> default-originate [route-map <name>]
    neighbor <ip> maximum-prefix <n> [<threshold>] [warning-only]
    neighbor <ip> soft-reconfiguration inbound
    neighbor <ip> fall-over bfd
    neighbor <ip> ttl-security-hops <n>
    neighbor <ip> local-as <asn> [no-prepend]
    neighbor <ip> weight <value>
    neighbor <ip> passive
    neighbor <ip> graceful-shutdown

    address-family ipv4 unicast
        neighbor <ip> activate
        network <prefix>/<len>
        redistribute {connected | static | ospf} [route-map <name>]
        aggregate-address <prefix>/<len> [summary-only] [as-set]
        neighbor <ip> add-paths {both | receive | send}
    exit-address-family

    address-family ipv6 unicast
        neighbor <ip> activate
        network <prefix>/<len>
        redistribute {connected | static | ospfv3} [route-map <name>]
    exit-address-family

    bgp bestpath as-path multipath-relax
    bgp bestpath as-path ignore
    bgp bestpath compare-routerid
    bgp bestpath med missing-as-worst
    bgp bestpath med confed
    bgp always-compare-med
    bgp deterministic-med
    bgp default local-preference <value>
    bgp cluster-id <x.x.x.x>
    bgp confederation identifier <asn>
    bgp confederation peers <asn> [<asn>...]
    bgp dampening [<half-life> <reuse> <suppress> <max-suppress-time>]
    bgp fast-external-fallover
    bgp log-neighbor-changes
    bgp maxas-limit <n>
    maximum-paths <n>
    distance bgp <external> <internal> <local>
    timers bgp <keepalive> <holdtime>
    bgp graceful-restart restart-time <seconds>
    bgp graceful-restart stalepath-time <seconds>
```

AOS-CX uses IOS-style `router bgp <asn>` configuration. Neighbors must be explicitly activated under each address-family with `neighbor <ip> activate`. Route advertisement uses `network` statements or `redistribute` commands within the address-family context. Route-maps and prefix-lists provide policy control per neighbor.

`ip routing` must be enabled globally before BGP will function. Without it, no routing protocol operates.

## VRF Configuration

```
router bgp <asn>
    vrf <vrf-name>
        bgp router-id <x.x.x.x>
        neighbor <ip> remote-as <asn>
        address-family ipv4 unicast
            neighbor <ip> activate
            network <prefix>/<len>
            redistribute connected
        exit-address-family
```

VRF BGP configuration is nested under `vrf <name>` within the `router bgp` block. VRF-aware show commands append `vrf <name>` or `all-vrfs`:
- `show bgp ipv4 unicast summary vrf <name>`
- `show bgp ipv4 unicast neighbors vrf <name>`
- `show bgp ipv4 unicast vrf <name>`
- `show bgp all-vrfs`

## Verification Commands

| Command | Purpose |
|---------|---------|
| `show bgp ipv4 unicast summary [vrf <name>]` | Peer states, prefixes received, AS numbers |
| `show bgp ipv4 unicast neighbors [vrf <name>]` | Full neighbor detail: state, timers, capabilities |
| `show bgp ipv4 unicast neighbors <ip> [vrf <name>]` | Single peer detail |
| `show bgp ipv4 unicast neighbors <ip> routes [vrf <name>]` | Routes received from a specific peer (post-policy) |
| `show bgp ipv4 unicast neighbors <ip> received-routes [vrf <name>]` | Routes received from a specific peer (pre-policy, requires `neighbor soft-reconfiguration inbound`) |
| `show bgp ipv4 unicast neighbors <ip> advertised-routes [vrf <name>]` | Routes advertised to a specific peer |
| `show bgp ipv4 unicast [vrf <name>]` | Full BGP table |
| `show bgp ipv4 unicast <prefix> [vrf <name>]` | Detail for a specific prefix |
| `show bgp ipv6 unicast summary` | IPv6 peer summary |
| `show ip route bgp [vrf <name>]` | BGP routes installed in the RIB |
| `show bgp summary [vrf <name>]` | Abbreviated peer summary (address-family-agnostic form) |
| `show bgp neighbors [<ip>] [vrf <name>]` | Neighbor detail (address-family-agnostic form) |
| `show bgp community <community>` | BGP table filtered by community value |
| `show bgp paths` | All BGP path entries in the table |
| `show bgp flap-statistics` | Route flap dampening statistics |
| `show bgp peer-group summary` | Summary for configured peer groups |
| `show running-config bgp` | BGP section of running configuration |

Note: AOS-CX uses `show bgp ipv4 unicast` not `show ip bgp`. The address-family qualifier is required for most show commands. Both the address-family form (`show bgp ipv4 unicast summary`) and the address-family-agnostic form (`show bgp summary`) are valid on AOS-CX.

## Clear / Reset Commands

| Command | Purpose |
|---------|---------|
| `clear bgp ipv4 unicast <ip>` | Hard reset (session teardown and re-establish) for a specific peer |
| `clear bgp ipv4 unicast <ip> soft` | Soft reset both directions for a specific peer |
| `clear bgp ipv4 unicast <ip> soft in` | Soft inbound reset — re-apply inbound policy without session reset (requires `neighbor soft-reconfiguration inbound`) |
| `clear bgp ipv4 unicast <ip> soft out` | Soft outbound reset — re-advertise outbound routes to peer |
| `clear bgp ipv4 unicast *` | Hard reset all BGP peers |
| `clear bgp ipv4 unicast * soft` | Soft reset all peers both directions |

Timer and policy changes require session reset to take effect unless soft reconfiguration is enabled. Use the soft forms to avoid dropping the session. The hard reset form (`clear bgp ipv4 unicast <ip>` without `soft`) tears down and re-establishes the TCP session.

## AOS-CX-Specific Defaults and Behaviors

- **Timer defaults**: Hold time 180s, keepalive 60s. Same as IOS, EOS, and VyOS. Different from JunOS which defaults to hold 90s / keepalive 30s.
- **Administrative distance**: eBGP = 20, iBGP = 200, local = 200. Same as IOS, EOS, and VyOS. Configurable with `distance bgp <external> <internal> <local>`.
- **Address family activation**: IPv4 unicast is NOT activated by default. Each neighbor must be explicitly activated under `address-family ipv4 unicast` with `neighbor <ip> activate`. Without activation, the peer will establish but exchange no routes.

- **`ip routing` required**: BGP will not function unless `ip routing` is enabled at the global config level. This is specific to AOS-CX -- IOS, EOS, and JunOS do not have this prerequisite.
- **Path selection**: Follows standard BGP best path algorithm. `bestpath as-path multipath-relax` allows ECMP across paths with different AS numbers but equal AS-path length. `bestpath compare-routerid` uses router-id as final tiebreaker instead of oldest path. `bestpath med missing-as-worst` treats missing MED as worst (4294967295) rather than best (0).

- **Graceful restart**: Supported and configurable. `graceful-restart` enables the feature. Default restart-time and stalepath-time are vendor-specific. Helper mode is enabled by default.
- **Route reflection**: `neighbor <ip> route-reflector-client` designates a peer as a route-reflector client. Cluster-id defaults to the router-id.
- **Maximum paths**: ECMP for BGP. Default is 1 (no ECMP). Configure with `maximum-paths <n>` under the address-family.

- **Authentication**: MD5 via `neighbor <ip> password <key>`. TCP-AO is also available via `neighbor <ip> ao` (AOS-CX 6300/6400 series). This contrasts with OSPF which supports SHA. Verify platform support — not all AOS-CX hardware supports TCP-AO for BGP.
- **Show command structure**: AOS-CX uses `show bgp ipv4 unicast` not `show ip bgp`. Both the address-family-qualified form (`show bgp ipv4 unicast summary`) and the address-family-agnostic form (`show bgp summary`) are valid. This differs from IOS (`show ip bgp`) and JunOS (`show bgp`).
- **Neighbor shutdown**: `neighbor <ip> shutdown` administratively disables a peer without removing configuration. Useful for maintenance windows.
- **Soft reconfiguration**: `neighbor <ip> soft-reconfiguration inbound` enables storage of pre-policy routes from a peer. Required to use `show bgp ipv4 unicast neighbors <ip> received-routes` and `clear bgp ipv4 unicast <ip> soft in` without triggering a hard reset.
- **BFD integration**: `neighbor <ip> fall-over bfd` enables BFD for fast peer failure detection. Requires BFD to be configured on the interface. Provides sub-second failure detection vs. the default hold-timer-based detection.
- **Route dampening**: `bgp dampening` suppresses flapping routes. Default half-life is 15 minutes, reuse threshold 750, suppress threshold 2000, max-suppress-time 60 minutes. Configured at the router bgp level, not per address-family on AOS-CX.
- **Graceful shutdown**: `neighbor <ip> graceful-shutdown` sends the GRACEFUL_SHUTDOWN community (65535:0) to a peer, triggering remote routers to deprioritize paths through this device before maintenance. Different from `neighbor <ip> shutdown` which immediately drops the session.
- **Fast external fallover**: `bgp fast-external-fallover` (enabled by default on AOS-CX) immediately resets eBGP sessions when the directly connected interface goes down, rather than waiting for hold timer expiry.
- **Confederation**: `bgp confederation identifier <asn>` sets the confederation AS. Member AS numbers are defined with `bgp confederation peers`. Confederation peers use iBGP-style relationships within the confederation but appear as eBGP to external peers.
- **ADD-PATH**: `neighbor <ip> add-paths {both | receive | send}` enables per-peer ADD-PATH (RFC 7911). Must be activated under the address-family context. Allows advertisement of multiple paths to a neighbor rather than only the best path.
- **Default local-preference**: `bgp default local-preference <value>` sets the default LOCAL_PREF for routes received from iBGP peers. Default is 100. Lower value = less preferred. Applicable only within an AS.
- **Neighbor weight**: `neighbor <ip> weight <value>` sets Cisco-style weight for routes from a specific peer. Weight is local only (not propagated). Higher weight = more preferred. Takes precedence over local-preference in best-path selection. Default weight is 0 for learned routes, 32768 for locally originated routes.
- **TTL security (GTSM)**: `neighbor <ip> ttl-security-hops <n>` enables Generalized TTL Security Mechanism (RFC 5082). The router expects BGP packets with TTL >= (255 - hops). Prevents off-link spoofing. Mutually exclusive with `ebgp-multihop`.
- **Local-as override**: `neighbor <ip> local-as <asn> [no-prepend]` presents a different AS number to a specific peer. Useful for AS migrations. Without `no-prepend`, both the real AS and the configured local-as appear in the AS path. With `no-prepend`, only the local-as is prepended.
- **log-neighbor-changes**: `bgp log-neighbor-changes` logs BGP peer state transitions (up/down/reset). Enabled by default on AOS-CX. Generates syslog entries for operational visibility.

## Configuration Revert Patterns

**General rule**: Prefix any command with `no` to revert to default. Changes take effect immediately.

```
no neighbor <ip> remote-as                # removes the neighbor entirely
no neighbor <ip> route-map <name> in      # removes inbound route-map
no neighbor <ip> route-map <name> out     # removes outbound route-map
no neighbor <ip> password                 # removes authentication
no neighbor <ip> timers                   # reverts to 60/180 defaults
no neighbor <ip> timers connect-retry     # reverts connect-retry to default
no neighbor <ip> shutdown                 # re-enables the neighbor
no neighbor <ip> next-hop-self            # reverts next-hop behavior
no neighbor <ip> soft-reconfiguration inbound  # disables inbound soft-reconfig
no neighbor <ip> fall-over bfd            # disables BFD for this neighbor
no neighbor <ip> send-community           # stops sending community attributes
no neighbor <ip> maximum-prefix           # removes prefix limit
no neighbor <ip> default-originate        # stops advertising default to this peer
no neighbor <ip> allowas-in              # reverts to rejecting own-AS routes
no neighbor <ip> weight                   # reverts weight to default (0)
no network <prefix>/<len>                 # removes network advertisement
no redistribute <protocol>               # removes redistribution
no maximum-paths                          # reverts to 1 (no ECMP)
no bgp dampening                          # disables route flap dampening
no bgp log-neighbor-changes               # disables peer state logging
no bgp always-compare-med                 # reverts MED comparison to same-AS only
no bgp default local-preference           # reverts local-preference default to 100
no bgp fast-external-fallover             # disables immediate reset on link-down
```

**Non-obvious exceptions**:

| Scenario | Correct sequence | Gotcha |
|----------|-----------------|--------|
| Remove neighbor entirely | `no neighbor <ip> remote-as` | Removes the neighbor and ALL its sub-config (timers, policies, activation). NOT `no neighbor <ip>`. |
| Remove from address-family | Under `address-family`: `no neighbor <ip> activate` | De-activates the peer for that family. Peering stays up but stops exchanging routes for that AFI. |
| Revert timers | `no neighbor <ip> timers` | Reverts to global `timers bgp` setting, or 60/180 if no global timers configured. Change takes effect on next session reset. |
| Revert authentication | `no neighbor <ip> password` | Both sides must remove or change auth simultaneously. Mismatch causes TCP RST on every connection attempt. |
| Remove VRF BGP | Under `router bgp <asn>`: `no vrf <name>` | Removes all BGP config for that VRF including neighbors, networks, and redistribution. |

## Common Gotchas on AOS-CX

- `show bgp ipv4 unicast` not `show ip bgp`. The address-family qualifier is mandatory for table lookups. Automation parsers written for IOS must be adapted.
- `ip routing` must be enabled globally. Without it, BGP (and all routing protocols) will not operate. This is a platform requirement not found on IOS or EOS.
- Neighbors must be explicitly activated under each address-family. A configured neighbor with `remote-as` but no `activate` will establish TCP session but exchange zero routes.
- The `neighbors` plural form is used in show commands: `show bgp ipv4 unicast neighbors`, not `show bgp ipv4 unicast neighbor`.
- VRF BGP is configured under `vrf <name>` within the `router bgp` block, not as a separate `router bgp <asn> vrf <name>` command.
- `no neighbor <ip> remote-as` removes the entire neighbor config. There is no standalone `no neighbor <ip>` form.
- MED comparison is only between paths from the same AS by default. Use `bgp always-compare-med` to compare MED across paths from different ASes. Use `bgp bestpath med missing-as-worst` to treat missing MED as highest value rather than 0 (best).
- Timer changes require session reset to take effect. Use `clear bgp ipv4 unicast <ip> soft` for a soft reset that applies policy without dropping the session. Use `clear bgp ipv4 unicast <ip>` (no `soft`) for a hard reset that tears down and re-establishes TCP.
- `show bgp ipv4 unicast neighbors <ip> received-routes` requires `neighbor <ip> soft-reconfiguration inbound` to be configured. Without it, pre-policy routes are not stored and the command returns no output.
- `neighbor <ip> ttl-security-hops` and `neighbor <ip> ebgp-multihop` are mutually exclusive. Configuring both causes a conflict.
- `bgp fast-external-fallover` is enabled by default on AOS-CX. It resets eBGP sessions immediately when the connected interface goes down. Disable with `no bgp fast-external-fallover` if sessions should persist through brief link flaps.
- `bgp log-neighbor-changes` is enabled by default. Peer state transitions appear in syslog. Disable explicitly with `no bgp log-neighbor-changes` if syslog volume is a concern.
- The graceful-restart syntax changed between releases. In 10.14, use `bgp graceful-restart restart-time` and `bgp graceful-restart stalepath-time` (with `bgp` prefix), not the legacy `graceful-restart restart-time` form without the prefix.

## Key RFCs

- **RFC 4271** -- A Border Gateway Protocol 4 (BGP-4): Core protocol specification
- **RFC 4760** -- Multiprotocol Extensions for BGP-4: IPv4/IPv6 unicast address families
- **RFC 4724** -- Graceful Restart Mechanism for BGP: Graceful restart support
- **RFC 4456** -- BGP Route Reflection: Route reflector client configuration
- **RFC 7911** -- Advertisement of Multiple Paths in BGP (ADD-PATH): Multiple path advertisement
- **RFC 4893** -- BGP Support for Four-Octet AS Number Space: 4-byte ASN support
- **RFC 1997** -- BGP Communities Attribute: Standard community attribute (`neighbor send-community`)
- **RFC 4360** -- BGP Extended Communities Attribute: Extended community attribute (`neighbor send-community extended`)
- **RFC 2439** -- BGP Route Flap Damping: Route dampening specification (`bgp dampening`)
- **RFC 5082** -- The Generalized TTL Security Mechanism (GTSM): TTL security for BGP (`neighbor ttl-security-hops`)
- **RFC 5492** -- Capabilities Advertisement with BGP-4: Capability negotiation used by ADD-PATH and ORF
- **RFC 8538** -- Notification Message Support for BGP Graceful Restart: GRACEFUL_SHUTDOWN community (`neighbor graceful-shutdown`)
- **RFC 5065** -- Autonomous System Confederations for BGP: BGP confederation support
