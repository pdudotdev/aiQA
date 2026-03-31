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
    neighbor <ip> route-map <name> {in | out}
    neighbor <ip> prefix-list <name> {in | out}
    neighbor <ip> shutdown
    neighbor <ip> description <text>
    neighbor <ip> next-hop-self
    neighbor <ip> route-reflector-client

    address-family ipv4 unicast
        neighbor <ip> activate
        network <prefix>/<len>
        redistribute {connected | static | ospf} [route-map <name>]
        aggregate-address <prefix>/<len> [summary-only] [as-set]
    exit-address-family

    address-family ipv6 unicast
        neighbor <ip> activate
        network <prefix>/<len>
        redistribute {connected | static | ospfv3} [route-map <name>]
    exit-address-family

    bgp bestpath as-path multipath-relax
    bgp bestpath compare-routerid
    bgp bestpath med missing-as-worst
    maximum-paths <n>
    distance bgp <external> <internal> <local>
    timers bgp <keepalive> <holdtime>
    graceful-restart
    graceful-restart restart-time <seconds>
    graceful-restart stalepath-time <seconds>
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
| `show bgp ipv4 unicast neighbors <ip> routes [vrf <name>]` | Routes received from a specific peer |
| `show bgp ipv4 unicast neighbors <ip> advertised-routes [vrf <name>]` | Routes advertised to a specific peer |
| `show bgp ipv4 unicast [vrf <name>]` | Full BGP table |
| `show bgp ipv4 unicast <prefix> [vrf <name>]` | Detail for a specific prefix |
| `show bgp ipv6 unicast summary` | IPv6 peer summary |
| `show ip route bgp [vrf <name>]` | BGP routes installed in the RIB |

Note: AOS-CX uses `show bgp ipv4 unicast` not `show ip bgp`. The address-family qualifier is required in all show commands. `show bgp` alone without a family qualifier is not valid.

## AOS-CX-Specific Defaults and Behaviors

- **Timer defaults**: Hold time 180s, keepalive 60s. Same as IOS, EOS, and VyOS. Different from JunOS which defaults to hold 90s / keepalive 30s.
- **Administrative distance**: eBGP = 20, iBGP = 200, local = 200. Same as IOS, EOS, and VyOS. Configurable with `distance bgp <external> <internal> <local>`.
- **Address family activation**: IPv4 unicast is NOT activated by default. Each neighbor must be explicitly activated under `address-family ipv4 unicast` with `neighbor <ip> activate`. Without activation, the peer will establish but exchange no routes.

- **`ip routing` required**: BGP will not function unless `ip routing` is enabled at the global config level. This is specific to AOS-CX -- IOS, EOS, and JunOS do not have this prerequisite.
- **Path selection**: Follows standard BGP best path algorithm. `bestpath as-path multipath-relax` allows ECMP across paths with different AS numbers but equal AS-path length. `bestpath compare-routerid` uses router-id as final tiebreaker instead of oldest path. `bestpath med missing-as-worst` treats missing MED as worst (4294967295) rather than best (0).

- **Graceful restart**: Supported and configurable. `graceful-restart` enables the feature. Default restart-time and stalepath-time are vendor-specific. Helper mode is enabled by default.
- **Route reflection**: `neighbor <ip> route-reflector-client` designates a peer as a route-reflector client. Cluster-id defaults to the router-id.
- **Maximum paths**: ECMP for BGP. Default is 1 (no ECMP). Configure with `maximum-paths <n>` under the address-family.

- **Authentication**: MD5 only via `neighbor <ip> password <key>`. No SHA or TCP-AO variants for BGP (unlike OSPF which supports SHA).
- **Show command structure**: AOS-CX uses `show bgp ipv4 unicast` not `show ip bgp`. The address-family qualifier (`ipv4 unicast` or `ipv6 unicast`) is mandatory. This differs from IOS (`show ip bgp`) and JunOS (`show bgp`).
- **Neighbor shutdown**: `neighbor <ip> shutdown` administratively disables a peer without removing configuration. Useful for maintenance windows.

## Configuration Revert Patterns

**General rule**: Prefix any command with `no` to revert to default. Changes take effect immediately.

```
no neighbor <ip> remote-as                # removes the neighbor entirely
no neighbor <ip> route-map <name> in      # removes inbound route-map
no neighbor <ip> route-map <name> out     # removes outbound route-map
no neighbor <ip> password                 # removes authentication
no neighbor <ip> timers                   # reverts to 60/180 defaults
no neighbor <ip> shutdown                 # re-enables the neighbor
no neighbor <ip> next-hop-self            # reverts next-hop behavior
no network <prefix>/<len>                 # removes network advertisement
no redistribute <protocol>               # removes redistribution
no maximum-paths                          # reverts to 1 (no ECMP)
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

- `show bgp ipv4 unicast` not `show ip bgp`. The address-family qualifier is mandatory. Automation parsers written for IOS must be adapted.
- `ip routing` must be enabled globally. Without it, BGP (and all routing protocols) will not operate. This is a platform requirement not found on IOS or EOS.
- Neighbors must be explicitly activated under each address-family. A configured neighbor with `remote-as` but no `activate` will establish TCP session but exchange zero routes.
- The `neighbors` plural form is used in show commands: `show bgp ipv4 unicast neighbors`, not `show bgp ipv4 unicast neighbor`.
- VRF BGP is configured under `vrf <name>` within the `router bgp` block, not as a separate `router bgp <asn> vrf <name>` command.
- `no neighbor <ip> remote-as` removes the entire neighbor config. There is no standalone `no neighbor <ip>` form.
- MD5 authentication is the only option for BGP peering. SHA and TCP-AO are not available for BGP on AOS-CX.
- MED comparison is only between paths from the same AS by default. Use `bestpath med missing-as-worst` to treat missing MED as highest value rather than 0 (best).
- Timer changes require session reset to take effect. Use `clear bgp ipv4 unicast <ip>` to reset a specific peer after timer changes.

## Key RFCs

- **RFC 4271** -- A Border Gateway Protocol 4 (BGP-4): Core protocol specification
- **RFC 4760** -- Multiprotocol Extensions for BGP-4: IPv4/IPv6 unicast address families
- **RFC 4724** -- Graceful Restart Mechanism for BGP: Graceful restart support
- **RFC 4456** -- BGP Route Reflection: Route reflector client configuration
- **RFC 7911** -- Advertisement of Multiple Paths in BGP (ADD-PATH): Multiple path advertisement
- **RFC 4893** -- BGP Support for Four-Octet AS Number Space: 4-byte ASN support
