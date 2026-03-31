# BGP on Juniper JunOS

## Configuration Syntax

```
set protocols bgp group <name> type {internal | external}
set protocols bgp group <name> peer-as <asn>
set protocols bgp group <name> local-as <asn>
set protocols bgp group <name> neighbor <ip>
set protocols bgp group <name> neighbor <ip> peer-as <asn>

set protocols bgp group <name> export <policy-name>
set protocols bgp group <name> import <policy-name>

set protocols bgp group <name> family inet unicast
set protocols bgp group <name> family inet6 unicast
set protocols bgp group <name> family inet-vpn unicast

set protocols bgp group <name> local-address <ip>
set protocols bgp group <name> multihop [ttl <value>]
set protocols bgp group <name> authentication-key <key>
set protocols bgp group <name> authentication-algorithm <md5 | hmac-sha-1-96 | ao>

set protocols bgp group <name> hold-time <seconds>
set protocols bgp group <name> keep-all
set protocols bgp group <name> keep-none
set protocols bgp group <name> log-updown
set protocols bgp group <name> passive
set protocols bgp group <name> cluster <cluster-id>
set protocols bgp group <name> allow <prefix/len>

set protocols bgp local-as <asn>
set protocols bgp path-selection always-compare-med
set protocols bgp path-selection external-router-id
set protocols bgp precision-timers
set protocols bgp graceful-restart

set routing-options router-id <x.x.x.x>
set routing-options autonomous-system <asn>
```

JunOS requires all BGP neighbors to be configured within a named group. Groups define the peer type (`internal` or `external`), address families, and policies. Neighbors inherit group-level settings but can override them. An explicit `export` policy is required to advertise routes to BGP peers -- there is no implicit `network` or `redistribute` command as on IOS-style platforms. The `import` policy filters received routes before they enter the routing table.

The autonomous system number is configured under `[edit routing-options]`, not under `[edit protocols bgp]`. Router ID is also set under `[edit routing-options]`.

## VRF (Routing Instance) Configuration

```
set routing-instances <vrf-name> instance-type vrf
set routing-instances <vrf-name> interface <name>
set routing-instances <vrf-name> route-distinguisher <rd>
set routing-instances <vrf-name> vrf-target <rt>
set routing-instances <vrf-name> protocols bgp group <name> type {internal | external}
set routing-instances <vrf-name> protocols bgp group <name> neighbor <ip> peer-as <asn>
```

VRF-aware show commands use `instance <vrf-name>`:
- `show bgp summary instance <vrf>`
- `show bgp neighbor instance <vrf>`
- `show route table <vrf>.inet.0 protocol bgp`

## Verification Commands

| Command | Purpose |
|---------|---------|
| `show bgp summary` | Peer states, prefixes received, AS numbers |
| `show bgp neighbor` | Full neighbor detail: state, timers, capabilities, options |
| `show bgp neighbor <ip>` | Single peer detail |
| `show bgp group` | Group-level summary: type, peer count, active prefixes |
| `show bgp group <name>` | Single group detail |
| `show route protocol bgp` | BGP routes in the routing table |
| `show route advertising-protocol bgp <peer-ip>` | Routes advertised to a specific peer |
| `show route receive-protocol bgp <peer-ip>` | Routes received from a specific peer (before import policy) |
| `show bgp neighbor <ip> flap-statistics` | Route flap damping statistics for a peer |
| `show route table inet.0 protocol bgp detail` | Detailed BGP route attributes (AS-path, MED, local-pref, communities) |

Note: JunOS uses `show bgp` with no `ip` prefix -- it is not `show ip bgp` as on IOS, EOS, or AOS-CX.

## JunOS-Specific Defaults and Behaviors

- **Timer defaults**: Hold time 90s, keepalive 30s (1/3 of hold). This is different from IOS, EOS, AOS-CX, and VyOS which default to hold 180s / keepalive 60s. In mixed-vendor peerings, the lower hold time (90s) will be negotiated per RFC 4271.
- **Route preference (AD equivalent)**: eBGP = 170, iBGP = 170. Both use the same preference value. This differs significantly from IOS/EOS/AOS-CX/VyOS where eBGP = 20 and iBGP = 200. Route selection between eBGP and iBGP relies on path selection, not preference.
- **Export policy required**: JunOS will NOT advertise any BGP routes without an explicit `export` policy. There is no `network` statement or `redistribute` command. This is the most common cause of "peering is up but no routes" issues on JunOS.

- **BGP groups mandatory**: All neighbors must belong to a named group. There is no way to configure a standalone neighbor without a group. Groups define inheritance for policies, families, and timers.
- **Address family activation**: Unlike IOS where IPv4 unicast is active by default, JunOS requires explicit `family inet unicast` configuration. Without it, the peer will not exchange IPv4 routes.
- **Path selection**: JunOS compares MED only between paths from the same neighboring AS by default. Enable `path-selection always-compare-med` to compare across all ASes. `external-router-id` uses router-id as a tiebreaker for external paths (default: oldest path wins).

- **Graceful restart**: Enabled by default per RFC 4724. Allows non-disruptive control-plane restarts while forwarding continues. Same default as EOS and AOS-CX.
- **Route reflection**: Configure with `cluster <cluster-id>` on the group. All iBGP peers in that group become route-reflector clients.
- **Passive peering**: `passive` keyword on a group or neighbor makes JunOS wait for incoming TCP connections rather than initiating them. Useful for dynamic peer groups with `allow <prefix/len>`.

- **Authentication**: MD5 (`authentication-key`), HMAC-SHA-1-96, and TCP-AO (`authentication-algorithm ao`) supported. MD5 is the most common. Authentication is configured per-group or per-neighbor.
- **AS number location**: The local AS is configured under `[edit routing-options autonomous-system]`, not under `[edit protocols bgp]`. The `local-as` under a group overrides for that group only (useful for AS migration).

## Configuration Revert Patterns

**General rule**: `delete <config-path>` removes a configuration statement and reverts to default. All changes are staged in candidate config and require `commit` to activate. JunOS provides built-in config versioning -- `rollback <n>` (0=current, 1=previous, up to 49) lets you restore any prior committed config, followed by `commit`.

```
delete protocols bgp group <name> neighbor <ip>
delete protocols bgp group <name> peer-as
delete protocols bgp group <name> export
delete protocols bgp group <name> import
delete protocols bgp group <name> hold-time
delete protocols bgp group <name> authentication-key
delete protocols bgp group <name> local-as
delete protocols bgp group <name> multihop
delete protocols bgp group <name> family inet unicast
delete protocols bgp group <name>                         # removes entire group
```

After any `delete`, run `commit` to activate. Optionally use `commit confirmed <minutes>` for a timed safety net -- if you don't re-commit within the window, config automatically rolls back.

**Built-in rollback**:

```
rollback 1    # restore previous committed config
commit        # activate the rollback
```

**Non-obvious exceptions**:

| Scenario | Correct sequence | Gotcha |
|----------|-----------------|--------|
| Remove a single neighbor | `delete protocols bgp group <name> neighbor <ip>` + `commit` | Removing the last neighbor in a group does NOT remove the group itself. The empty group persists. |
| Remove entire group | `delete protocols bgp group <name>` + `commit` | Removes all neighbors, policies, and families in one operation. |
| Revert hold-time | `delete protocols bgp group <name> hold-time` + `commit` | Reverts to 90s default (not 180s as on IOS-style). Peer will renegotiate on next session reset. |
| Revert export policy | `delete protocols bgp group <name> export` + `commit` | Without an export policy, NO routes will be advertised. This is a traffic-impacting change. |
| Revert authentication | `delete protocols bgp group <name> authentication-key` + `commit` | Both sides must remove auth simultaneously or the session will drop and not recover. |

## Common Gotchas on JunOS

- `show bgp` has no `ip` prefix -- it is not `show ip bgp` as on IOS, EOS, or AOS-CX.
- Export policy is REQUIRED to advertise routes. Without it, BGP peering comes up but zero routes are sent. This is the number one JunOS BGP misconfiguration.
- BGP groups are mandatory -- you cannot configure a neighbor without first creating a group. There is no flat neighbor configuration.
- `family inet unicast` must be explicitly configured. Without address family activation, no IPv4 routes are exchanged even if peering is established.
- Hold time defaults to 90s, not 180s. In mixed-vendor environments, the lower value is negotiated. If the remote side expects 180s keepalives at 60s intervals, the JunOS peer will send keepalives at 30s.
- Route preference for BGP is 170 (both eBGP and iBGP), not 20/200 as on IOS-style platforms. This means OSPF internal (preference 10) always beats BGP, but OSPF external (150) also beats BGP (170).
- AS number is configured under `[edit routing-options autonomous-system]`, not under `[edit protocols bgp]`. Forgetting this causes BGP to not start.
- `show route advertising-protocol bgp <peer>` shows what is actually being sent after export policy. `show route receive-protocol bgp <peer>` shows what was received before import policy. These are essential debugging tools.
- `show bgp summary` output format differs from IOS `show ip bgp summary` -- columns and state representations are different. Automation parsers must be platform-specific.
- `deactivate protocols bgp group <name>` disables a group without deleting config. Useful for maintenance. Reactivate with `activate`.

## Key RFCs

- **RFC 4271** -- A Border Gateway Protocol 4 (BGP-4): Core protocol specification
- **RFC 4760** -- Multiprotocol Extensions for BGP-4: Address family support (inet, inet6, inet-vpn)
- **RFC 4724** -- Graceful Restart Mechanism for BGP: Default-enabled on JunOS
- **RFC 5291** -- Outbound Route Filtering Capability for BGP-4: ORF support
- **RFC 4456** -- BGP Route Reflection: Route reflector cluster-id and client configuration
- **RFC 5082** -- The Generalized TTL Security Mechanism (GTSM): Multihop TTL security
