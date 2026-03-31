# BGP on MikroTik RouterOS 7

## Configuration Syntax

RouterOS 7 uses a connection-based BGP model completely different from IOS-style vendors and from RouterOS 6:

```
/routing bgp template
add name=<name> as=<local-asn> router-id=<x.x.x.x>
set <template> hold-time=<time> keepalive-time=<time>
set <template> address-families=<ip,ipv6,l2vpn,l2vpn-vpls,vpnv4>
set <template> routing-table=<name>
set <template> input.filter=<chain-name>
set <template> output.filter-chain=<chain-name>
set <template> output.network=<prefix-list-name>
set <template> multihop=<yes|no>
set <template> nexthop-choice=<default|force-self|propagate>
set <template> cluster-id=<x.x.x.x>
set <template> as-override=<yes|no>
set <template> remove-private-as=<yes|no>

/routing bgp connection
add name=<name> remote.address=<ip> remote.as=<asn> local.role=<ebgp|ibgp|ebgp-peer|ibgp-peer>
set <connection> template=<template-name>
set <connection> local.address=<ip>
set <connection> address-families=<ip,ipv6,vpnv4>
set <connection> hold-time=<time>
set <connection> keepalive-time=<time>
set <connection> input.filter=<chain-name>
set <connection> output.filter-chain=<chain-name>
set <connection> output.network=<prefix-list-name>
set <connection> multihop=<yes|no>
set <connection> disabled=<yes|no>
set <connection> tcp-md5-key=<key>
set <connection> routing-table=<name>

/routing bgp connection
add name=peer1 remote.address=10.0.0.2 remote.as=65002 template=default \
    local.role=ebgp address-families=ip
```

Configuration is object-based: templates define shared defaults, connections define individual peerings. Connections inherit settings from their assigned template but can override any property. The `local.role` field (`ebgp`, `ibgp`, `ebgp-peer`, `ibgp-peer`) replaces the group-type concept of JunOS and determines session behavior per RFC 9234.

Route advertisement uses `output.network` (references a prefix list of networks to originate) and `output.filter-chain` (routing filter for policy). There is no `network` statement or `redistribute` command in the IOS sense. Filtering uses routing filter rules defined under `/routing filter rule`.

## VRF (Routing Table) Configuration

```
/routing table
add name=VRF1 fib

/routing bgp template
add name=vrf1-bgp as=65001 routing-table=VRF1

/routing bgp connection
add name=vrf1-peer1 remote.address=10.0.0.2 remote.as=65002 \
    template=vrf1-bgp local.role=ebgp routing-table=VRF1
```

RouterOS uses "routing tables" as its VRF concept. The `routing-table` parameter on the template or connection binds BGP to a specific VRF (default: `main`). VRFs are defined under `/routing table` with a `fib` flag.

RouterOS BGP commands do not have VRF-specific show variants. All sessions are visible together; filter by connection name or routing-table to isolate a VRF.

## Verification Commands

| Command | Purpose |
|---------|---------|
| `/routing bgp session print detail without-paging` | Session state, timers, capabilities, prefixes received/sent |
| `/routing bgp session print terse without-paging` | Compact session table (one line per peer) |
| `/routing bgp advertisements print without-paging` | Routes being advertised to peers |
| `/routing bgp connection print detail without-paging` | Connection configuration (remote AS, template, families) |
| `/routing bgp template print detail without-paging` | Template configuration (shared settings) |
| `/ip route print where bgp without-paging` | BGP routes installed in the main routing table |
| `/ip route print where routing-table=<vrf> and bgp without-paging` | BGP routes in a specific VRF |
| `/routing stats print without-paging` | General routing statistics including BGP counters |
| `/routing bgp session print count-only` | Number of BGP sessions (quick health check) |

Note: Always append `without-paging` for scripted/SSH access. Use `terse` for compact tabular output or `detail` for verbose key-value output. There is no `show` keyword -- RouterOS uses `print` style commands.

## RouterOS-Specific Defaults and Behaviors

- **Timer defaults**: Hold time 180s (3m), keepalive 60s (1m). Same as IOS, EOS, AOS-CX, and VyOS. Different from JunOS which defaults to hold 90s / keepalive 30s.
- **Administrative distance**: eBGP = 20, iBGP = 200. Same as IOS, EOS, AOS-CX, and VyOS. Routes install with standard BGP distances.
- **Connection-based model**: RouterOS 7 replaced the instance-based BGP model of RouterOS 6. Old ROS6 commands (`/routing bgp instance`, `/routing bgp peer`, `/routing bgp network`) do not work on ROS7. The entire paradigm changed to template/connection objects.

- **local.role field**: Defines the BGP role per RFC 9234 (BGP Roles). Values: `ebgp` (external, initiates), `ibgp` (internal, initiates), `ebgp-peer` (external, passive), `ibgp-peer` (internal, passive). This replaces the `type internal/external` concept of JunOS and the implicit role detection of IOS-style vendors.
- **Address families**: Configured per-template or per-connection with `address-families=<list>`. Supported: `ip`, `ipv6`, `l2vpn`, `l2vpn-vpls`, `vpnv4`. Default is `ip`. Unlike IOS, families are set as a property, not entered as a sub-mode.

- **Route origination**: Uses `output.network` referencing a firewall address-list or prefix-list of networks to originate. This replaces the `network` statement of IOS-style vendors. Routes must exist in the routing table to be originated (unless using filter-based origination).
- **Filtering**: `input.filter` filters received routes. `output.filter-chain` filters advertised routes. Both reference routing filter chains under `/routing filter rule`. These replace route-maps and are more similar to JunOS policies.

- **Path selection**: Standard BGP best-path algorithm. MED comparison is between paths from the same AS by default. No `always-compare-med` toggle exists as a named option -- behavior is controlled through routing filters.
- **Graceful restart**: Supported. Enabled by default on templates. Allows non-disruptive restarts while peers maintain forwarding state.
- **Route reflection**: Configure with `cluster-id` on the template. Connections using that template treat peers as route-reflector clients.
- **Authentication**: TCP MD5 only via `tcp-md5-key` on the connection. No SHA or TCP-AO variants for BGP.

## Configuration Revert Patterns

**General rule**: RouterOS uses an object-based model. Revert approaches depend on whether you're resetting a property or removing an object entirely.

- **Reset a property to default**: `set <id> <property>=` (empty value) -- e.g., `set 0 hold-time=` resets hold-time to default on connection #0
- **Remove an object**: `remove <id>` -- deletes the connection or template entirely
- **Disable without removing**: `set <id> disabled=yes` -- administratively disables the connection
- Changes take effect immediately (no commit step).

```
# Reset connection properties
/routing bgp connection
set <id> hold-time=              # reset to 3m (180s)
set <id> keepalive-time=         # reset to 1m (60s)
set <id> input.filter=           # remove inbound filter
set <id> output.filter-chain=    # remove outbound filter
set <id> output.network=         # stop originating networks
set <id> tcp-md5-key=            # remove authentication
set <id> multihop=no             # disable multihop

# Disable a connection
/routing bgp connection
set <id> disabled=yes            # administratively disable

# Remove a connection entirely
/routing bgp connection
remove <id>

# Remove a template
/routing bgp template
remove <id>
```

**Non-obvious exceptions**:

| Scenario | Correct sequence | Gotcha |
|----------|-----------------|--------|
| Disable a peer | `set <id> disabled=yes` | Does NOT remove config. Re-enable with `disabled=no`. |
| Remove authentication | `set <id> tcp-md5-key=` (empty) | Both sides must remove auth simultaneously or session drops and cannot recover. |
| Reset hold-time | `set <id> hold-time=` (empty) | Reverts to template value if set, or 3m default. Session resets on next keepalive miss. |
| Remove connection | `remove <id>` | Removes the connection and tears down the session immediately. Template remains. |
| Remove template in use | `remove <id>` | Fails if any connection references the template. Remove or reassign connections first. |

## Common Gotchas on RouterOS

- RouterOS 7 BGP is completely restructured from RouterOS 6. Old ROS6 commands (`/routing bgp peer`, `/routing bgp instance`, `/routing bgp network`) do not exist. Migration requires full reconfiguration.
- Forgetting `without-paging` causes SSH sessions to hang waiting for user input.
- The `+ct` suffix on username (e.g., `admin+ct`) disables colors and auto-completion for clean output parsing in automation.
- There is no `show` keyword. All commands use `/routing bgp session print` style. Automation scripts must adapt.
- `local.role` is mandatory on connections. Omitting it causes cryptic errors. Use `ebgp` for external peers, `ibgp` for internal peers.
- Address families default to `ip` only. IPv6 peering requires explicit `address-families=ipv6` or `address-families=ip,ipv6`.
- `output.network` requires a matching route in the routing table to originate the prefix. Unlike IOS `network`, there is no option to originate without a matching route.
- Template properties are inherited by connections but can be overridden. Changing a template property affects all connections using it unless they override that property.
- No per-VRF show command variants. All BGP sessions appear together; filter output by connection name or routing-table to isolate VRF data.
- `terse` vs `detail` on `print` changes output format significantly. Automation parsers must specify the format explicitly.

## Key RFCs

- **RFC 4271** -- A Border Gateway Protocol 4 (BGP-4): Core protocol specification
- **RFC 4760** -- Multiprotocol Extensions for BGP-4: Address family support (ip, ipv6, vpnv4)
- **RFC 9234** -- Route Leak Prevention and Detection Using Roles in UPDATE and OPEN Messages: local.role field
- **RFC 4724** -- Graceful Restart Mechanism for BGP: Graceful restart support
- **RFC 4456** -- BGP Route Reflection: Route reflector cluster-id and client configuration
- **RFC 2385** -- Protection of BGP Sessions via the TCP MD5 Signature Option: TCP MD5 authentication
