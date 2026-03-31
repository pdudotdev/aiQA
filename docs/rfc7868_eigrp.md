# EIGRP Protocol Reference (RFC 7868 — Cisco's Enhanced Interior Gateway Routing Protocol)

## DUAL Algorithm

EIGRP uses the Diffusing Update Algorithm (DUAL) to guarantee loop-free routing at every instant. DUAL maintains three distance values per destination per neighbor:

- **Reported Distance (RD)**: The total metric to the destination as advertised by a neighbor. This is the neighbor's own best metric to that destination.
- **Computed Distance (CD)**: The total metric from the local router through a specific neighbor: CD = cost_to_neighbor + neighbor's RD.
- **Feasible Distance (FD)**: The lowest CD ever seen for this destination since the last ACTIVE-to-PASSIVE transition. FD is a historical minimum, not necessarily the current best metric.

### Feasibility Condition

A neighbor satisfies the Feasibility Condition (FC) when: **neighbor's RD < local router's FD**. This guarantees the neighbor is closer to the destination than this router has ever been, which proves the path through that neighbor is loop-free.

### Successor and Feasible Successor

- **Successor**: The neighbor providing the least-cost path (lowest CD) that also passes FC. This is the active next-hop installed in the routing table.
- **Feasible Successor**: Any other neighbor that passes FC. These are pre-computed backup paths that can be used instantly without a DUAL recomputation.

### Route States

- **PASSIVE**: At least one successor exists. The route is stable and usable.
- **ACTIVE**: No neighbor passes FC after a topology change. The route is unusable while DUAL sends QUERYs and waits for REPLYs from all neighbors.

## DUAL Finite State Machine

DUAL runs a per-destination finite state machine. Each prefix maintains its own independent state — there is no global FSM synchronization.

### States

| State | Description |
|-------|-------------|
| PASSIVE | Route is stable. Successor exists. No outstanding QUERYs. |
| ACTIVE (oij=0) | Local origin. QUERY sent to all neighbors. No REPLY from successor yet. |
| ACTIVE (oij=1) | Local origin. REPLY received from successor but not all neighbors. |
| ACTIVE (oij=2) | QUERY received from successor triggered ACTIVE. No REPLY from successor yet. |
| ACTIVE (oij=3) | QUERY received from successor triggered ACTIVE. REPLY received from successor but not all neighbors. |

### Key Transitions

- **PASSIVE → ACTIVE**: Topology change (link down, metric increase) causes FC to fail for all neighbors. Router sends QUERY to every neighbor.
- **ACTIVE → PASSIVE**: All queried neighbors have sent REPLYs. Router selects new successor (or removes route if no path exists).
- **QUERY from non-successor while PASSIVE**: If a feasible successor exists, the route stays PASSIVE and the router sends a REPLY immediately.

## Packet Types

EIGRP runs directly over IP using protocol number 88 (not TCP or UDP). Packets are sent to multicast address **224.0.0.10** (IPv4) or **FF02::A** (IPv6), with unicast used for retransmissions and targeted updates.

| Opcode | Name | Delivery | Purpose |
|--------|------|----------|---------|
| 1 | UPDATE | Reliable (multicast/unicast) | Carries destination reachability and metric changes |
| 3 | QUERY | Reliable (multicast) | Requests alternate paths when route goes ACTIVE |
| 4 | REPLY | Reliable (unicast) | Response to QUERY with destination metric |
| 5 | HELLO | Unreliable (multicast) | Neighbor discovery and keepalive |
| 10 | SIA-QUERY | Reliable (multicast) | Checks if neighbor is still converging (SIA prevention) |
| 11 | SIA-REPLY | Reliable (unicast) | Confirms ongoing convergence to SIA-QUERY sender |

An **ACK** is not a separate opcode — it is a HELLO packet (opcode 5) with a non-zero Acknowledgment Number field.

## Header Flags and TLVs

### Header Flags

The EIGRP fixed header includes a 4-byte Flags field. Defined flag bits:

| Flag | Bit | Purpose |
|------|-----|---------|
| INIT | 0x01 | Set in the first UPDATE to a new neighbor (NULL UPDATE). Instructs the neighbor to send its full topology. |
| CR | 0x02 | Conditional Receive. Recipients listed in the SEQUENCE TLV process normally; all others discard. |
| RS | 0x04 | Restart. Indicates the sender is restarting (graceful restart / NSF). |
| EOT | 0x08 | End-of-Table. Marks the last UPDATE in the initial topology exchange. |

### TLV Types

EIGRP encodes all payload data as Type-Length-Value elements.

**Generic TLVs** (carried in HELLO, UPDATE, and other packets):

| Code | Name | Purpose |
|------|------|---------|
| 0x0001 | PARAMETER | K-values and hold time |
| 0x0002 | AUTHENTICATION | MD5 or SHA2 auth data |
| 0x0003 | SEQUENCE | Lists neighbors for targeted multicast (CR mode) |
| 0x0004 | SOFTWARE_VERSION | IOS/firmware version of sender |
| 0x0005 | MULTICAST_SEQUENCE | Next multicast sequence number |
| 0x0006 | PEER_INFORMATION | Peer capabilities and flags |
| 0x0007 | PEER_TERMINATION | Graceful neighbor shutdown |
| 0x0008 | TID_LIST | Topology Identifier list (multi-topology) |

**Route TLVs** (carried in UPDATE, QUERY, REPLY):

| Code | Name | Scope |
|------|------|-------|
| 0x0102 | IPv4 Internal | IPv4 routes within the EIGRP AS |
| 0x0103 | IPv4 External | IPv4 redistributed routes |
| 0x0104 | IPv4 Community | IPv4 community tags |
| 0x0606 | IPv6 Internal | IPv6 routes within the EIGRP AS |
| 0x0607 | IPv6 External | IPv6 redistributed routes |
| 0x0608 | IPv6 Community | IPv6 community tags |
| 0x0F01 | Wide Metric Internal | Multi-protocol internal (wide metrics) |
| 0x0F02 | Wide Metric External | Multi-protocol external (wide metrics) |

## Neighbor Discovery and 3-Way Handshake

### Timers

| Parameter | Default | Notes |
|-----------|---------|-------|
| Hello interval | 5 seconds | Sent on all EIGRP-enabled interfaces |
| Hold time | 15 seconds | 3× hello interval. Neighbor declared dead if no packet received within hold time. |

Hold time resets on receipt of **any** EIGRP packet from the neighbor, not just HELLOs.

### Adjacency Requirements

Both routers must agree on:
- **K-values** (metric coefficients) — a K-value mismatch prevents adjacency formation entirely
- **AS number** — routers in different EIGRP autonomous systems do not form adjacencies
- **Common subnet** — interfaces must share an IP subnet (for directly connected neighbors)

### 3-Way Handshake Sequence

1. Router A detects Router B via multicast HELLO. Router B enters the neighbor table in a pending state.
2. Router A sends a unicast NULL UPDATE (INIT flag set, no route TLVs) to Router B.
3. Router B acknowledges the NULL UPDATE, sends its own NULL UPDATE with INIT flag.
4. Both routers exchange full topology via subsequent UPDATE packets. Adjacency is up once all updates are acknowledged.

## Reliable Transport Protocol (RTP)

EIGRP implements its own reliable transport layer rather than using TCP:

- **Sequence numbers**: Each reliable packet carries a monotonically increasing sequence number. Wraps to 1 at maximum value (sequence 0 is reserved for unreliable packets like HELLO).
- **Acknowledgments**: Each packet is individually acknowledged. There is no windowing — one outstanding packet per neighbor at a time.
- **Retransmission**: If an ACK is not received, the packet is retransmitted up to **16 times over 5 seconds**. After 16 failed retransmissions, the neighbor adjacency is reset.
- **Multicast first, unicast retry**: Initial transmissions use multicast. If a specific neighbor fails to ACK, retransmissions switch to unicast for that neighbor only.

### Conditional Receive (CR) Mode

When a neighbor's retransmission queue is full (slow neighbor), the router enters CR mode: it sends a HELLO with a SEQUENCE TLV listing neighbors that should process the next multicast. Neighbors not in the list set their CR flag and discard the next multicast packet (they will receive it via unicast retransmission instead). This prevents one slow neighbor from blocking multicast delivery to all others.

## Metric Calculation

### Classic Metrics

The classic composite metric formula:

```
metric = 256 × { (K1 × BW) + [(K2 × BW) / (256 - LOAD)] + (K3 × DELAY) } × (K5 / (REL + K4))
```

**Default K-values**: K1 = 1, K2 = 0, K3 = 1, K4 = 0, K5 = 0, K6 = 0.

When K5 = 0 the reliability term equals 1, and with K2 = 0 the load term drops out. The simplified default formula:

```
metric = 256 × ( (10^7 / BWmin_kbps) + sum_of_delays )
```

- **Bandwidth (BW)**: Inverse of the minimum bandwidth along the path, scaled to kbps: `10^7 / BWmin`. Uses the slowest link in the path.
- **Delay**: Cumulative sum of all outgoing interface delays along the path, in tens of microseconds.
- **Unreachable**: A delay value of 0xFFFFFFFF signals an unreachable destination (infinite metric). This encoding is used in QUERY packets.

### Wide Metrics

Classic metrics use 32-bit values that cannot distinguish between high-speed links (10G, 40G, 100G all compute to the same BW component). Wide metrics extend to 64-bit precision:

- **EIGRP_WIDE_SCALE** = 65536 (scaling factor for wide metric computation)
- **EIGRP_CLASSIC_SCALE** = 256 (legacy scaling factor)
- **Delay**: Measured in picoseconds instead of tens of microseconds
- **Backward compatibility**: Wide metric ÷ (EIGRP_WIDE_SCALE / EIGRP_CLASSIC_SCALE) = classic metric. This allows mixed classic/wide-metric routers in the same domain.

Wide metric TLVs (0x0F01, 0x0F02) also support extended attributes: jitter, energy, and administrator tags via sub-TLVs.

## Split Horizon

Split horizon prevents routing loops on multi-access segments by suppressing route advertisements back through the interface where the route was learned.

- **Split horizon (default)**: Do not advertise a route out the interface through which the successor route was learned.
- **Poison reverse**: Advertise the route out the learned interface, but with an unreachable metric (delay = 0xFFFFFFFF). This accelerates convergence by explicitly informing the neighbor the path is invalid.

Split horizon should be **disabled** on hub-and-spoke topologies (DMVPN, Frame Relay) where spoke-to-spoke reachability requires the hub to re-advertise routes back out the same interface.

## Stub Routing

Stub routers advertise limited routing information and are shielded from QUERY propagation. A stub declares its role via flags in the HELLO packet's PEER_INFORMATION TLV.

### Stub Flags

| Flag | Behavior |
|------|----------|
| CONNECTED | Advertise directly connected networks |
| STATIC | Advertise redistributed static routes |
| SUMMARY | Advertise summary (aggregated) routes |
| RECEIVE-ONLY | Accept routes from neighbors but advertise nothing |

### Query Handling

Hub routers (non-stubs) do **not** send QUERYs to stub neighbors. If a stub receives a QUERY, it responds immediately with an unreachable metric rather than propagating the QUERY further. This prevents SIA conditions caused by downstream stub networks and dramatically reduces convergence time in large hub-and-spoke deployments.

## Stuck-In-Active (SIA) Handling

When a route enters ACTIVE state, a timer begins. If not all REPLYs arrive before the timer expires, the route is Stuck-In-Active:

| Event | Time | Action |
|-------|------|--------|
| Route goes ACTIVE | 0 s | QUERY sent to all neighbors. SIA timer starts. |
| Half SIA interval | 90 s | SIA-QUERY sent to each non-responding neighbor. |
| SIA-REPLY received | — | Timer resets for that neighbor. Confirms neighbor is still actively converging. |
| Full SIA interval | 180 s | If neighbor has not sent REPLY or SIA-REPLY: adjacency with that neighbor is reset. |

Up to 3 SIA-QUERY/SIA-REPLY cycles can occur. Each SIA-REPLY resets the timer for another 90 seconds. A neighbor that never responds within the full SIA interval is torn down — all routes through that neighbor are removed and the adjacency is re-established from scratch.

## External Routes

External routes are prefixes redistributed into EIGRP from another protocol (OSPF, BGP, static, connected). They are carried in External route TLVs (0x0103, 0x0607, 0x0F02) and tagged with:

- **Originating Router ID**: The router that performed the redistribution
- **Originating AS Number**: The EIGRP AS where redistribution occurred
- **External Protocol ID**: Source protocol (OSPF, RIP, BGP, static, connected)
- **External Protocol Metric**: The original metric in the source protocol
- **Administrator Tag**: Optional 32-bit tag for route-map filtering (0–4294967295)

### Route Preference

EIGRP **always** prefers internal routes over external routes to the same destination, regardless of metric values. Among external routes, lower metric wins.

| Route Type | Typical Administrative Distance |
|------------|-------------------------------|
| EIGRP internal (same AS) | 90 |
| EIGRP summary | 5 |
| EIGRP external (redistributed) | 170 |

## Authentication

EIGRP supports packet authentication to prevent unauthorized routers from injecting routes:

- **MD5**: HMAC-MD5 message authentication. Key ID field allows multiple keys for hitless rotation.
- **SHA2**: HMAC-SHA-256, SHA-384, or SHA-512. Stronger alternative to MD5.

Authentication provides **integrity only** — EIGRP payloads are not encrypted. Both sides of a link must use the same authentication type and key. Mismatched authentication prevents adjacency formation (packets are silently discarded).

Authentication data is carried in the AUTHENTICATION TLV (0x0002). Key chains with multiple key IDs and lifetimes enable key rotation without adjacency disruption.

## Key RFCs

- **RFC 7868**: Cisco's Enhanced Interior Gateway Routing Protocol (EIGRP) — full protocol specification including DUAL, packet formats, RTP, metrics, and stub routing
- **RFC 2328**: OSPFv2 — commonly co-deployed with EIGRP; redistribution between the two is a frequent design pattern
- **RFC 7311**: AIGP Metric Attribute for BGP — analogous wide-metric considerations for BGP
