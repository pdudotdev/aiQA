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
set protocols bgp group <name> no-enforce-first-as        # disable first-AS check (default: enforced)
set protocols bgp group <name> metric-out <value>         # set fixed MED sent to this group
set protocols bgp group <name> metric-out igp             # set MED to IGP cost at time of advertisement
set protocols bgp group <name> metric-out igp <offset>    # IGP cost + offset
set protocols bgp group <name> metric-out minimum-igp     # minimum IGP cost observed
set protocols bgp group <name> metric-out minimum-igp <offset>
set protocols bgp group <name> metric-out delay-med-update # defer MED updates until IGP converges

set protocols bgp local-as <asn>
set protocols bgp path-selection always-compare-med
set protocols bgp path-selection external-router-id
set protocols bgp path-selection as-path-ignore           # skip AS-path length as tiebreaker
set protocols bgp path-selection cisco-non-deterministic  # evaluate paths in receipt order (Cisco legacy mode)
set protocols bgp path-selection med-plus-igp             # add IGP cost to MED before comparing
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
| `show route hidden` | Routes received but not installed: failed import policy, enforce-first-as rejection, etc. |
| `show route hidden detail` | Hidden routes with the reason for rejection |

Note: JunOS uses `show bgp` with no `ip` prefix -- it is not `show ip bgp` as on IOS, EOS, or AOS-CX.

**`show bgp summary` output columns**: `Peer` — neighbor IP, `AS` — peer AS, `InPkt`/`OutPkt` — packets received/sent, `OutQ` — output queue depth, `Flaps` — session flap count, `Last Up/Dwn` — time since last state change, `State/#Active/Received/Accepted/Damped` — when established: active/received/accepted (after import policy)/damped prefix counts. State "Establ" means the session is up.

## JunOS-Specific Defaults and Behaviors

- **Timer defaults**: Hold time 90s, keepalive 30s (1/3 of hold). This is different from IOS, EOS, AOS-CX, and VyOS which default to hold 180s / keepalive 60s. In mixed-vendor peerings, the lower hold time (90s) will be negotiated per RFC 4271.
- **Route preference (AD equivalent)**: eBGP = 170, iBGP = 170. Both use the same preference value. This differs significantly from IOS/EOS/AOS-CX/VyOS where eBGP = 20 and iBGP = 200. Note: OSPF internal has preference 10 (always beats BGP), OSPF external has preference 150 (also beats BGP at 170).
- **Export policy required**: JunOS will NOT advertise any BGP routes without an explicit `export` policy. There is no `network` statement or `redistribute` command. This is the most common cause of "peering is up but no routes" issues on JunOS.
- **RFC 8212 NOT enforced**: JunOS does not implement RFC 8212 default-deny behavior for eBGP. Routes are accepted from eBGP peers even without an explicit import policy (though an export policy is still required for outbound advertisement). This is intentional for backward compatibility.
- **Router ID default**: If `routing-options router-id` is not configured, JunOS selects the IP of the first interface found during initialization — not necessarily the loopback. Always configure an explicit router-id.
- **MED default (missing attribute)**: A received BGP route with no MED attribute is treated as MED 0 (best) during path selection. Routes without MED are preferred over routes with a non-zero MED when `always-compare-med` is enabled.
- **`enforce-first-as` (default ON)**: For eBGP peers, JunOS verifies that the first AS in the received AS_PATH matches the configured `peer-as`. Routes that fail this check are marked hidden (not installed in the routing table). Visible with `show route hidden`. Disable per-group with `no-enforce-first-as`.
- **`local-address` required for loopback iBGP**: When iBGP peers are addressed via loopback interfaces, `local-address` must be explicitly configured on the group. Without it, JunOS sources the TCP connection from an interface IP rather than the loopback, and the session may fail to establish.
- **iBGP full mesh requirement**: All iBGP speakers in the same AS must be in a full mesh unless route reflection (`cluster`) or confederation is used. A route learned from one iBGP peer is not re-advertised to other iBGP peers (iBGP split horizon per RFC 4271).
- **SRX security zone requirement**: On SRX platforms, BGP will not establish unless the security zone containing the peering interface explicitly permits the protocol: `set security zones security-zone <zone> host-inbound-traffic protocols bgp`. Without this, the SRX silently drops BGP TCP (port 179) destined for the routing engine.
- **`metric-out`**: JunOS does not set MED by default. Use `metric-out <value>` to send a fixed MED, or `metric-out igp` to set MED to the IGP cost of the route. `delay-med-update` defers MED changes until after IGP convergence to prevent transient oscillation.

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
| Revert metric-out | `delete protocols bgp group <name> metric-out` + `commit` | JunOS stops sending MED to this group's peers. Remote side may reorder paths. |
| Revert always-compare-med | `delete protocols bgp path-selection always-compare-med` + `commit` | Reverts to per-AS MED comparison only. Best paths may change on peers with multiple upstreams. |
| Revert no-enforce-first-as | `delete protocols bgp group <name> no-enforce-first-as` + `commit` | Re-enables first-AS check. Routes from peers whose first AS doesn't match peer-as become hidden. |

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
- Routes rejected by import policy or failing `enforce-first-as` are marked hidden — not installed in the routing table. They are NOT visible in `show route protocol bgp`. Use `show route hidden` to see them and understand why they were rejected.
- `enforce-first-as` is ON by default — the first AS in a received AS_PATH must match `peer-as`. Violations silently reject the route into hidden state. Disable with `no-enforce-first-as` if peering through an AS that legitimately prepends differently.
- JunOS does NOT enforce RFC 8212 (no routes without policy). Routes are accepted from eBGP peers even without an import policy. Export policy is still required for outbound.
- On SRX platforms: configure `set security zones security-zone <zone> host-inbound-traffic protocols bgp` or BGP TCP will be silently dropped.
- `local-address` is required for iBGP sessions sourced from a loopback. Without it, the session may use a wrong source IP and fail or oscillate.

## Key RFCs

- **RFC 4271** -- A Border Gateway Protocol 4 (BGP-4): Core protocol specification
- **RFC 4760** -- Multiprotocol Extensions for BGP-4: Address family support (inet, inet6, inet-vpn)
- **RFC 4724** -- Graceful Restart Mechanism for BGP: Default-enabled on JunOS
- **RFC 5291** -- Outbound Route Filtering Capability for BGP-4: ORF support
- **RFC 4456** -- BGP Route Reflection: Route reflector cluster-id and client configuration
- **RFC 5082** -- The Generalized TTL Security Mechanism (GTSM): Multihop TTL security
- **RFC 4893** -- BGP Support for Four-Octet AS Number Space (32-bit ASNs): supported under `routing-options autonomous-system`
- **RFC 8212** -- Default EBGP Route Propagation Behavior without Policies: JunOS explicitly does NOT implement this for backward compatibility
