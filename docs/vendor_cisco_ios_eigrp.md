# EIGRP on Cisco IOS / IOS-XE

## Configuration Syntax

```
router eigrp <as-number>
 eigrp router-id <x.x.x.x>
 network <network> [<wildcard>]
 no auto-summary
 redistribute <protocol> [metric <bw> <delay> <rel> <load> <mtu>] [route-map <name>]
 default-metric <bw> <delay> <rel> <load> <mtu>
 passive-interface [default] [<interface>]
 variance <multiplier>
 maximum-paths <number>
 traffic-share balanced
 distance eigrp <internal> <external>
 offset-list [<acl>] {in | out} <offset> [<interface>]
 metric weights <tos> <k1> <k2> <k3> <k4> <k5>
 eigrp stub {connected | static | summary | receive-only | redistributed}
 eigrp log-neighbor-changes
 eigrp log-neighbor-warnings [<seconds>]
 eigrp event-log-size <size>
!
interface <name>
 ip hello-interval eigrp <as> <seconds>
 ip hold-time eigrp <as> <seconds>
 ip bandwidth-percent eigrp <as> <percent>
 ip summary-address eigrp <as> <network> <mask> [<admin-distance>] [leak-map <name>]
 no ip split-horizon eigrp <as>
 no ip next-hop-self eigrp <as>
 ip authentication mode eigrp <as> md5
 ip authentication key-chain eigrp <as> <keychain-name>
 ip dampening-change eigrp <as> [<percentage>]
 ip dampening-interval eigrp <as> [<seconds>]
```

IOS/IOS-XE supports both classic mode (`router eigrp <as-number>`) and named mode (`router eigrp <instance-name>`). Classic mode is widely deployed but named mode is preferred on modern IOS-XE — it supports wider metrics, per-AF configuration, and a cleaner hierarchy. A maximum of 30 EIGRP routing processes can be configured per device. The AS number must match on both sides of a neighbor relationship.

The `network` statement uses wildcard masks (not subnet masks) and determines which interfaces participate in EIGRP. Without a wildcard, the classful boundary is assumed. Per-interface timers and authentication are configured under the physical or logical interface in classic mode.

## Named Mode Configuration

```
router eigrp <instance-name>
 address-family ipv4 unicast autonomous-system <as>
  eigrp router-id <x.x.x.x>
  network <network> [<wildcard>]
  metric weights <tos> <k1> <k2> <k3> <k4> <k5> <k6>
  metric rib-scale <factor>
  neighbor <ip-address> <interface-type> <interface-number>
  af-interface { default | <interface-type> <interface-number> }
   hello-interval <seconds>
   hold-time <seconds>
   bandwidth-percent <maximum-bandwidth-percentage>
   dampening-change [<percentage>]
   dampening-interval [<seconds>]
   authentication mode md5
   authentication key-chain <name>
   summary-address <network> <mask> [<admin-distance>] [leak-map <name>]
   split-horizon | no split-horizon
   no next-hop-self [no-ecmp-mode]
   passive-interface
  exit-af-interface
  topology base
   variance <multiplier>
   maximum-paths <number>
   traffic-share balanced
   redistribute <protocol> [route-map <name>]
   redistribute static
   offset-list [<acl>] {in | out} <offset> [<interface>]
   summary-metric <network/prefix> <bw> <delay> <rel> <load> <mtu>
   no auto-summary
   eigrp event-log-size <size>
  exit-af-topology
  eigrp log-neighbor-changes
  eigrp log-neighbor-warnings [<seconds>]
```

Named mode consolidates interface-level EIGRP settings under `af-interface` within the address-family, eliminating the need for per-interface commands in classic mode. `af-interface default` applies settings to all interfaces in the address-family; `af-interface <interface>` overrides for a specific interface. Topology-level commands (variance, maximum-paths, redistribute, offset-list) go under `topology base`. Named mode enables wide metrics by default (rib-scale 128), providing finer-grained path selection on high-bandwidth links. The `metric weights` command in named mode accepts a 6th K-value (K6) for extended attributes. The `neighbor` command defines static peers for non-broadcast networks — the interface must be specified.

## VRF Configuration

```
router eigrp <instance-name>
 address-family ipv4 vrf <vrf-name> [unicast | multicast] autonomous-system <as>
  eigrp router-id <x.x.x.x>
  network <network> [<wildcard>]
```

VRF support requires named mode. Each VRF gets its own `address-family` block with an independent AS number and router-id. The optional `unicast` or `multicast` keyword selects the subaddress family (unicast is the default). A VRF instance and route distinguisher must be defined before the address family session can be created. Only a single VRF can be supported by each VPN, and redistribution between different VRFs is not supported. VRF-aware show commands append `vrf <name>`:
- `show ip eigrp vrf <name> neighbors`
- `show ip eigrp vrf <name> topology`
- `show ip route vrf <name> eigrp`

## Verification Commands

### Classic Mode

| Command | Purpose |
|---------|---------|
| `show ip eigrp neighbors` | Neighbor list: address, interface, hold time, uptime, SRTT, Q count |
| `show ip eigrp topology` | Topology table: successors and feasible successors for each prefix |
| `show ip eigrp topology all-links` | Full topology table including non-feasible paths |
| `show ip eigrp interfaces [detail]` | Per-interface: peers, xmit queue, pending routes, mean SRTT |
| `show ip eigrp traffic` | EIGRP packet statistics: hellos, updates, queries, replies, acks, SIA |
| `show ip eigrp events` | EIGRP event log (metric changes, route installs, FC checks) |
| `show ip eigrp accounting` | Prefix accounting per neighbor (prefix count, restart count) |
| `show ip route eigrp` | EIGRP routes installed in the RIB (internal D and external D EX) |
| `show running-config \| section eigrp` | Current EIGRP configuration |

### Named Mode

| Command | Purpose |
|---------|---------|
| `show eigrp address-family ipv4 [<as>] neighbors` | Neighbor list (named mode) |
| `show eigrp address-family ipv4 [<as>] topology` | Topology table (named mode) |
| `show eigrp address-family ipv4 [<as>] interfaces` | Interface details (named mode) |
| `show eigrp address-family ipv4 [<as>] timers` | Timer and expiration info |
| `show eigrp address-family ipv4 [<as>] traffic` | Packet statistics (named mode) |
| `show eigrp address-family ipv4 [<as>] events` | Event log (named mode) |
| `show eigrp protocols [vrf <name>]` | Protocol summary: K-values, max paths, distances, variance, hop count, active timer |
| `show eigrp plugins [detailed]` | EIGRP feature plugin versions |

## IOS-Specific Defaults and Behaviors

- **Router ID selection**: (1) explicit `eigrp router-id` command, (2) highest loopback IP, (3) highest active physical interface IP. Unlike OSPF, EIGRP does not require a process reset after changing the router-id — the change takes effect on the next neighbor establishment.

- **Hello interval**: 5 seconds for all networks; 60 seconds for low-speed nonbroadcast multiaccess (NBMA) networks. Low speed is T1 or slower, as specified with the `bandwidth` interface command. Frame Relay and SMDS are considered NBMA only if the interface has not been configured to use physical multicasting. Hold time: 15 seconds for all networks; 180 seconds for NBMA. Range for both: 1–65535 seconds. Hold time should be at least 3x hello interval — if no packet is received within the hold time, the neighbor is declared down.
- **K-values**: K1=1, K2=0, K3=1, K4=0, K5=0 by default. Named mode adds K6=0 (extended attributes). K-values must match on both sides of a neighbor relationship — a mismatch silently prevents adjacency.
- **Classic metric formula**: `metric = 256 * ((K1*BW) + (K2*BW)/(256-Load) + (K3*Delay)) * (K5/(Reliability+K4))`. When K5=0, the reliability term equals 1. Default simplification: `256 * (10^7/BWmin_kbps + cumulative_delay/10)`. Delay is in tens of microseconds; divide by 10 for the formula.
- **Wide metric formula (named mode)**: `metric = 256 * ((K1*Throughput) + (K2*Throughput)/(256-Load) + (K3*Latency) + (K6*Extended_Attributes)) * (K5/(Reliability+K4))`. Uses 64-bit values; Throughput and Latency replace BW and Delay for higher precision on fast links.

- **Administrative distance**: Internal routes = 90, Summary routes = 5, External routes = 170. Configurable with `distance eigrp <internal> <external>`.
- **Auto-summary**: Enabled by default. Use `no auto-summary` to disable. When enabled, EIGRP advertises only classful network boundaries, suppressing subnets. Always disable in modern networks with VLSM/CIDR.

- **Maximum-paths**: 4 by default. Supports up to 32 equal-cost paths (16 on older platforms). Only equal-cost paths are used unless variance is configured.
- **Variance**: 1 by default (equal-cost only). Setting variance > 1 enables unequal-cost load balancing. A route is eligible if its metric is less than variance * the successor's metric, and the route passes the feasibility condition. Use `traffic-share balanced` to distribute traffic proportionally to metric.
- **Maximum hop count**: 100 by default (configurable). The EIGRP metric is large enough to support thousands of hops.
- **Max processes**: A maximum of 30 EIGRP routing processes can be configured per device.

- **Split horizon**: Enabled by default on all interfaces except ATM interfaces and subinterfaces, where it is disabled by default. On Frame Relay or DMVPN hub interfaces in hub-and-spoke topologies, disable with `no ip split-horizon eigrp <as>` (classic) or `no split-horizon` under `af-interface` (named) to allow spoke-to-spoke route propagation.
- **Next-hop-self**: Enabled by default — EIGRP sets the next-hop to the local outbound interface address, even when advertising routes back out the same interface. Disable with `no ip next-hop-self eigrp <as>` (classic) or `no next-hop-self [no-ecmp-mode]` under `af-interface` (named). The `no-ecmp-mode` keyword evaluates all paths in the topology table (not just the first entry) to determine if routes were learned on the same interface. Disabling next-hop-self is primarily useful in DMVPN spoke-to-spoke topologies.
- **Dampening**: Named mode supports metric dampening per af-interface. `dampening-change <percentage>` (default 50%) sets the minimum metric change threshold before advertising; `dampening-interval <seconds>` (default 30s, range 1–65535) limits update frequency. Both reduce churn from flapping links.

- **Stub**: Not configured by default. `eigrp stub` with no arguments enables `connected` and `summary` flags. Stub routers respond to queries with an immediate reply, reducing SIA events. The `receive-only` flag prevents the stub from advertising any routes.
- **Bandwidth percent**: 50% by default. EIGRP limits control traffic to 50% of the configured interface bandwidth. On shared WAN links or low-bandwidth interfaces, adjust with `ip bandwidth-percent eigrp <as> <percent>` (classic) or `bandwidth-percent` under `af-interface` (named).
- **SIA timer**: 180 seconds (3 minutes, confirmed by `show eigrp protocols` Active Timer field). If a query is not answered within this time, the neighbor is declared Stuck-In-Active and the adjacency is torn down.

- **Wide metrics**: Enabled by default in named mode (rib-scale 128). Classic mode uses 32-bit metrics; named mode uses 64-bit wide metrics that provide finer granularity on links above 1 Gbps. The `metric rib-scale <factor>` command controls the scaling factor for RIB installation.
- **Offset-list**: Adjusts incoming or outgoing route metrics by adding an offset. Available in classic mode and under `topology base` in named mode. IPv4 only — not supported for IPv6 configurations.
- **Goodbye message**: Broadcast when an EIGRP routing process is shut down. Allows peers to detect the shutdown immediately instead of waiting for the hold timer to expire. Devices running older software may misinterpret the goodbye message as a K-value mismatch.
- **Log-neighbor-changes**: Enabled by default. The system logs EIGRP neighbor adjacency changes to help monitor routing stability.
- **NSF-aware route hold timer**: 240 seconds. Graceful restart helper mode enabled by default — the router assists neighbors performing a non-disruptive restart without withdrawing their routes.

## Configuration Revert Patterns

**General rule**: Prefix any interface or process command with `no` to restore the default. Changes take effect immediately with no commit step.

```
no network <network> [<wildcard>]       # removes network statement
no redistribute <protocol>              # removes redistribution
no passive-interface <interface>        # re-enables EIGRP on interface
no ip hello-interval eigrp <as>        # reverts to 5s (or 60s on NBMA)
no ip hold-time eigrp <as>            # reverts to 15s (or 180s on NBMA)
no ip bandwidth-percent eigrp <as>     # reverts to 50%
no ip summary-address eigrp <as> <net> <mask>  # removes summary
no variance                            # reverts to 1 (equal-cost only)
no eigrp stub                         # removes stub configuration
no distance eigrp                     # reverts to 90/170
no default-metric                     # removes seed metric
no offset-list                        # removes offset-list
```

**Non-obvious exceptions**:

| Scenario | Correct sequence | Gotcha |
|----------|-----------------|--------|
| Revert authentication (classic) | 1. `no ip authentication mode eigrp <as> md5` 2. `no ip authentication key-chain eigrp <as>` | Two separate commands — disabling auth mode and removing the key-chain are independent operations |
| Revert auto-summary | `auto-summary` (to enable) or `no auto-summary` (to disable) | Auto-summary is enabled by default — adding `no auto-summary` disables classful summarization; removing it re-enables |
| Clear adjacencies | `clear ip eigrp neighbors` | Drops all EIGRP adjacencies immediately — highly disruptive. Use `clear ip eigrp neighbors <address>` to reset a single neighbor |
| Revert stub | `no eigrp stub` | All neighbors are reset when stub configuration is added or removed — adjacency flap is unavoidable |

## Common Gotchas on IOS

- K-value mismatch prevents adjacency formation with no explicit error message. The neighbor simply never appears in `show ip eigrp neighbors`. Verify with `show ip eigrp interfaces detail` — K-values are exchanged in Hello packets but mismatches produce no log entry by default. A goodbye message from a shutting-down neighbor may also be misinterpreted as a K-value mismatch on older IOS releases.
- AS number mismatch: the autonomous system number must match on both sides of a link. Unlike OSPF process IDs, the EIGRP AS number is carried in protocol packets and validated by the neighbor.
- Auto-summary is enabled by default. Subnets (e.g., 10.1.1.0/24) are summarized to classful boundaries (10.0.0.0/8), causing routing black holes when multiple sites share the same major network. Always configure `no auto-summary` in modern networks.
- Forgetting seed metric on `redistribute`: redistributed routes are not installed without an explicit metric. Use `redistribute <protocol> metric <bw> <delay> <rel> <load> <mtu>` or a `default-metric` statement. The five metric components are all required: bandwidth in kbps (10000 for Ethernet), delay in tens of microseconds (100 for Ethernet = 1 ms), reliability 0–255 (255 = 100%), load 1–255 (255 = fully loaded), MTU 1–65535 (1500 for Ethernet). The `default-metric` command does NOT affect redistributed connected routes — use `redistribute connected metric <bw> <delay> <rel> <load> <mtu>` explicitly.
- Split horizon on hub in hub-and-spoke DMVPN or Frame Relay blocks spoke-to-spoke route propagation. Disable with `no ip split-horizon eigrp <as>` on the hub interface. In named mode, also consider `no next-hop-self no-ecmp-mode` under af-interface for proper DMVPN spoke-to-spoke next-hop behavior.
- Passive interface in EIGRP suppresses both sending and receiving of Hello packets, preventing any adjacency on that interface. However, the interface address is still included in the topology database and advertised to other neighbors. This differs from OSPF, where passive-interface only suppresses Hello transmission.
- Stub misconfiguration: the `connected` flag advertises connected subnets but does not include redistributed static routes. Use `eigrp stub connected static` to advertise both. The `receive-only` flag overrides all other flags and prevents the stub from advertising any routes.
- SIA (Stuck-In-Active): if a router does not receive a reply to a query within 180 seconds (3 minutes), the unresponsive neighbor is declared SIA and the adjacency is torn down. Use stub routers and route summarization to limit the query domain and prevent SIA events.
- Named mode show commands use `show eigrp address-family` syntax, not `show ip eigrp`. Using classic show commands against a named-mode process may produce incomplete or empty output.
- Do not use `ip summary-address eigrp` to generate a default route (0.0.0.0/0) from an interface — this creates a summary with AD 5 pointing to Null0, which can displace the real default route and blackhole traffic. Use `distribute-list` to filter outbound advertisements instead.

## Key RFCs

| RFC | Title | Relevance |
|-----|-------|-----------|
| RFC 7868 | Cisco's Enhanced Interior Gateway Routing Protocol (EIGRP) | Defines EIGRP packet formats, DUAL algorithm, neighbor discovery, and protocol operation. The authoritative reference for EIGRP behavior. |
