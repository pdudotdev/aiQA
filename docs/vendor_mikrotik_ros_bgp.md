# BGP on MikroTik RouterOS 7

## Configuration Syntax

RouterOS 7 uses a connection-based BGP model completely different from IOS-style vendors and from RouterOS 6. Starting from v7.20, BGP instances must be explicitly defined in `/routing/bgp/instance` before connections can reference them.

```
# Explicit instance (required from v7.20+)
/routing bgp instance
add name=<name> as=<local-asn> router-id=<x.x.x.x>
set <instance> routing-table=<name>

# Template (shared settings inherited by connections)
/routing bgp template
add name=<name> as=<local-asn> router-id=<x.x.x.x>
set <template> hold-time=<time> keepalive-time=<time>
set <template> afi=<ip,ipv6,l2vpn,l2vpn-vpls,vpnv4>
set <template> routing-table=<name>
set <template> input.filter=<chain-name>
set <template> input.allow-as=<0..10>
set <template> input.ignore-aspath-len=<yes|no>
set <template> input.limit-process-routes-ipv4=<n>
set <template> input.limit-process-routes-ipv6=<n>
set <template> input.add-path=<ip|ipv6>
set <template> output.filter-chain=<chain-name>
set <template> output.network=<prefix-list-name>
set <template> output.redistribute=<bgp,connected,ospf,static,...>
set <template> output.default-originate=<always|if-installed|never>
set <template> output.as-override=<yes|no>
set <template> output.add-path=<ip|ipv6>
set <template> multihop=<yes|no>
set <template> nexthop-choice=<default|force-self|propagate>
set <template> cluster-id=<x.x.x.x>
set <template> remove-private-as=<yes|no>
set <template> use-bfd=<yes|no>

# Connection (individual peering)
/routing bgp connection
add name=<name> remote.address=<ip> remote.as=<asn> instance=<instance-name>
set <connection> local.role=<ebgp|ebgp-customer|ebgp-peer|ebgp-provider|ebgp-rs|ebgp-rs-client|ibgp|ibgp-rr>
set <connection> templates=<template-name>[,<template-name>]
set <connection> local.address=<ip>
set <connection> connect=<yes|no>
set <connection> listen=<yes|no>
set <connection> afi=<ip,ipv6,vpnv4>
set <connection> hold-time=<time>
set <connection> keepalive-time=<time>
set <connection> input.filter=<chain-name>
set <connection> output.filter-chain=<chain-name>
set <connection> output.network=<prefix-list-name>
set <connection> multihop=<yes|no>
set <connection> disabled=<yes|no>
set <connection> tcp-md5-key=<key>
set <connection> routing-table=<name>

# Minimal eBGP example (v7.20+)
/routing bgp instance
add name=i1 as=65001

/routing bgp connection
add name=toR2 remote.address=10.0.0.2 instance=i1 local.role=ebgp
```

Configuration is object-based: templates define shared defaults, connections define individual peerings. Connections inherit settings from their assigned `templates` (plural, comma-separated list) but can override any property. The `local.role` field determines session behavior per RFC 9234 — full list includes provider/customer/peer-server/route-server roles beyond the basic `ebgp`/`ibgp` options.

`remote.as` on a connection is optional — RouterOS can determine the remote AS automatically from the OPEN message. Useful for dynamic peer setups.

Route advertisement uses `output.network` (references an address-list of networks to originate — the matching IGP route must exist in the routing table) or `output.redistribute` (redistributes connected/static/ospf/bgp routes). There is no `network` statement or `redistribute` command in the IOS sense. Filtering uses routing filter chains under `/routing filter rule`.

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
| `/routing bgp instance print detail without-paging` | Instance configuration (v7.20+) |
| `/ip route print where bgp without-paging` | BGP routes installed in the main routing table |
| `/ip route print where routing-table=<vrf> and bgp without-paging` | BGP routes in a specific VRF |
| `/routing stats print without-paging` | General routing statistics including BGP counters |
| `/routing bgp session print count-only` | Number of BGP sessions (quick health check) |

**Session management commands** (run on a specific session by ID or name):

| Command | Effect |
|---------|--------|
| `/routing bgp session reset <id>` | Hard reset — tears down and re-establishes the session |
| `/routing bgp session stop <id>` | Stop the session without re-establishing |
| `/routing bgp session clear <id>` | Clear session flags (e.g., `limit-exceeded`) so the session can recover |
| `/routing bgp session refresh <id>` | Send route-refresh request — re-sends all routes from peer without dropping session |
| `/routing bgp session resend <id>` | Resend all advertised prefixes to the peer |

Note: Always append `without-paging` for scripted/SSH access. Use `terse` for compact tabular output or `detail` for verbose key-value output. There is no `show` keyword -- RouterOS uses `print` style commands.

## RouterOS-Specific Defaults and Behaviors

- **Timer defaults**: Hold time 180s (3m), keepalive 60s (1m). Same as IOS, EOS, AOS-CX, and VyOS. Different from JunOS which defaults to hold 90s / keepalive 30s.
- **Administrative distance**: eBGP = 20, iBGP = 200. Same as IOS, EOS, AOS-CX, and VyOS. Routes install with standard BGP distances.
- **Connection-based model**: RouterOS 7 replaced the instance-based BGP model of RouterOS 6. Old ROS6 commands (`/routing bgp instance`, `/routing bgp peer`, `/routing bgp network`) do not work on ROS7. The entire paradigm changed to template/connection objects.

- **local.role field**: Defines the BGP role per RFC 9234. Full set of values: `ebgp` (external, initiates), `ibgp` (internal, initiates), `ebgp-peer` (peer role, symmetric), `ebgp-customer` (customer in provider/customer model), `ebgp-provider` (provider in provider/customer model), `ebgp-rs` (route server), `ebgp-rs-client` (route server client), `ibgp-rr` (iBGP route-reflector). This replaces the `type internal/external` concept of JunOS and the implicit role detection of IOS-style vendors. `local.role` is mandatory on connections.

- **Address families (`afi`)**: Configured per-template or per-connection with `afi=<list>`. Supported: `ip`, `ipv6`, `l2vpn`, `l2vpn-vpls`, `vpnv4`, `vpnv6`, `evpn`. Default is `ip`. Unlike IOS, families are set as a property, not entered as a sub-mode. Note: the property is called `afi` in templates/instances but sometimes shown as `address-families` in older docs.

- **Route origination**: Uses `output.network` referencing an address-list of networks to originate — the matching IGP route **must** exist in the routing table. Use `output.redistribute` to redistribute connected/static/ospf/bgp route types. `output.default-originate=always|if-installed|never` controls default route advertisement (default: `never`).
- **Filtering**: `input.filter` filters received routes. `output.filter-chain` filters advertised routes. Both reference routing filter chains under `/routing filter rule`. These replace route-maps and are more similar to JunOS policies.
- **WEIGHT attribute**: RouterOS supports a WEIGHT attribute (not standard BGP — similar to Cisco's weight). Assigned via `input` routing filters, local to the router, not advertised to peers. Default is 0; higher value preferred. It is the first criterion in best-path selection.
- **Best-path selection order**: (1) WEIGHT (highest, local only, assigned via filter) → (2) LOCAL_PREF (highest, default 100) → (3) AS-PATH length (shortest, skip if `input.ignore-aspath-len=yes`) → (4) locally originated (aggregate/network) → (5) ORIGIN type (IGP < EGP < incomplete) → (6) eBGP over iBGP → (7) lowest IGP metric to next-hop → (8) if multipath enabled, stop here and install ECMP → (9) lowest router-id (or ORIGINATOR_ID if present) → (10) shortest cluster-list length → (11) lowest neighbor address.

- **Path selection**: Routes from different BGP instances are compared by general routing distance. Only routes from the same instance go through the BGP best-path algorithm.
- **Graceful restart**: Supported. Enabled by default on templates. Allows non-disruptive restarts while peers maintain forwarding state.
- **BFD integration**: `use-bfd=yes` on a template enables BFD for faster failure detection on that peer. Requires BFD to be configured separately.
- **Route reflection**: Configure with `cluster-id` on the template. Connections using that template become route-reflector clients. Use `output.no-client-to-client-reflection=yes` to disable C2C reflection.
- **Route limiting**: `input.limit-process-routes-ipv4=<n>` and `input.limit-process-routes-ipv6=<n>` limit the number of routes accepted per peer. When the limit is exceeded, the session flag `limit-exceeded` is set. Clear with `/routing bgp session clear <id>` to re-allow routes.
- **Authentication**: TCP MD5 only via `tcp-md5-key` on the connection. No SHA or TCP-AO variants for BGP.
- **`connect`/`listen`**: `connect=yes|no` controls whether RouterOS initiates outbound TCP connections. `listen=yes|no` controls whether it accepts incoming connections. Both default to `yes`. When `remote.address` is a subnet (dynamic peer), `listen=yes` keeps the listening socket open for up to 256 simultaneous incoming connections — use firewall to protect.
- **`remove-private-as`**: Strips private ASNs from AS-PATH before advertising. Applied before routing filters and before local AS prepend.
- **`output.as-override`**: Replaces all instances of the remote peer's AS number in AS-PATH with the local AS. Applied before routing filters and prepending. Used in scenarios where CE routers share the same ASN.
- **`input.allow-as`**: Allows the local AS to appear in received AS-PATH up to N times (0–10). Needed in certain hub-and-spoke or back-to-back VPN designs.
- **BGP unnumbered**: RouterOS supports BGP unnumbered connections (RFC 5549). Set `remote.address` to empty and `local.address` to an interface name. RouterOS uses IPv6 neighbor discovery to find the peer's link-local address. Requires IPv6 ND configured on the interface.

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
- **From v7.20+, explicit instances are required**: The old behavior where instances were auto-detected by matching router-ids no longer works. Every connection must reference an explicit `/routing bgp instance` entry via `instance=<name>`. Configs written for v7.1–v7.19 without explicit instances will not work on v7.20+.
- Forgetting `without-paging` causes SSH sessions to hang waiting for user input.
- The `+ct` suffix on username (e.g., `admin+ct`) disables colors and auto-completion for clean output parsing in automation.
- There is no `show` keyword. All commands use `/routing bgp session print` style. Automation scripts must adapt.
- `local.role` is mandatory on connections. Omitting it causes cryptic errors. Use `ebgp` for external peers, `ibgp` for internal peers.
- Address families default to `ip` only. IPv6 peering requires explicit `afi=ipv6` or `afi=ip,ipv6`.
- `output.network` requires a matching route in the routing table to originate the prefix. Unlike IOS `network`, there is no option to originate without a matching route. Use `output.network-blackhole=yes` to create a blackhole route for the network automatically.
- `templates` is plural and accepts a comma-separated list. Connections inherit settings from all listed templates; later templates override earlier ones. The connection itself can further override any property.
- Template properties are inherited by connections but can be overridden at the connection level. Changing a template property affects all connections using it unless they override that property.
- No per-VRF show command variants. All BGP sessions appear together; filter output by connection name or routing-table to isolate VRF data.
- `terse` vs `detail` on `print` changes output format significantly. Automation parsers must specify the format explicitly.
- After a session hits `input.limit-process-routes-ipv4/ipv6`, the flag `limit-exceeded` is set and the session stops accepting new routes. You must `/routing bgp session clear <id>` to reset the flag before routes flow again.
- `remote.as` on a connection is optional. If omitted, RouterOS determines the remote AS from the OPEN message. This enables flexible dynamic peer setups but removes the enforcement of expected AS numbers.

## Key RFCs

- **RFC 4271** -- A Border Gateway Protocol 4 (BGP-4): Core protocol specification
- **RFC 4760** -- Multiprotocol Extensions for BGP-4: Address family support (ip, ipv6, vpnv4)
- **RFC 9234** -- Route Leak Prevention and Detection Using Roles in UPDATE and OPEN Messages: local.role field
- **RFC 4724** -- Graceful Restart Mechanism for BGP: Graceful restart support
- **RFC 4456** -- BGP Route Reflection: Route reflector cluster-id and client configuration
- **RFC 2385** -- Protection of BGP Sessions via the TCP MD5 Signature Option: TCP MD5 authentication
- **RFC 2918** -- Route Refresh Capability for BGP-4: `refresh` session command
- **RFC 7911** -- Advertisement of Multiple Paths in BGP (Add-Path): `input.add-path` / `output.add-path`
- **RFC 1997** -- BGP Communities Attribute: Standard communities
- **RFC 8092** -- BGP Large Communities Attribute: Large community support
- **RFC 5065** -- Autonomous System Confederations for BGP: `as=<confederation_as>/<as>` format
- **RFC 5549** -- Advertising IPv4 Network Layer Reachability Information with an IPv6 Next Hop: BGP unnumbered
