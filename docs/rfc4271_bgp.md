# BGP-4 Protocol Reference (RFC 4271 — A Border Gateway Protocol 4)

## BGP Finite State Machine

BGP peers progress through six states to establish a session. The FSM is per-peer, not per-prefix.

### States

- **Idle**: Initial state. No TCP connection. Waiting for ManualStart or AutomaticStart event. On start, initializes ConnectRetryTimer and initiates TCP connection to peer.
- **Connect**: TCP connection in progress. If TCP succeeds, sends OPEN and transitions to OpenSent. If ConnectRetryTimer expires, transitions to Active.
- **Active**: Listening for incoming TCP connection. If TCP succeeds (inbound or outbound), sends OPEN and transitions to OpenSent. If ConnectRetryTimer expires, restarts in Connect.
- **OpenSent**: OPEN message sent, waiting for peer's OPEN. On valid OPEN received: negotiates hold time, sends KEEPALIVE, transitions to OpenConfirm. On NOTIFICATION: transitions to Idle.
- **OpenConfirm**: OPEN exchange complete, waiting for KEEPALIVE to confirm. On KEEPALIVE received: transitions to Established. On NOTIFICATION or hold timer expiry: transitions to Idle.
- **Established**: Session is up. UPDATE and KEEPALIVE messages are exchanged. Any error (NOTIFICATION, hold timer expiry, invalid message) transitions to Idle.

### Common Stuck States

| Stuck State | Most Likely Cause |
|-------------|-------------------|
| Idle | Peer unreachable (no TCP connectivity), wrong neighbor IP, AS number mismatch, administrative shutdown. |
| Active | TCP connection refused — remote BGP process not running, ACL blocking TCP port 179, or passive-only configuration on remote. |
| OpenSent | OPEN rejected — capability mismatch, unsupported AFI/SAFI, or authentication failure. |
| OpenConfirm | KEEPALIVE not received — hold time mismatch (one side sends 0, other expects >0), or packet loss. |

## Message Types

BGP uses TCP port 179. All messages share a common header:

- **Marker**: 16 octets, all ones (0xFF). Used for authentication in older implementations.
- **Length**: 2 octets. Minimum 19 (header only), maximum 4096.
- **Type**: 1 octet.

| Type | Name | Purpose |
|------|------|---------|
| 1 | OPEN | Initiates session. Carries version, AS number, hold time, BGP identifier, capabilities. |
| 2 | UPDATE | Advertises new routes and/or withdraws previously advertised routes. |
| 3 | NOTIFICATION | Signals an error condition. Session is closed after sending. |
| 4 | KEEPALIVE | Confirms peer is alive. Header only (19 octets, no payload). |

## OPEN Message

Sent immediately after TCP connection is established. Both peers must exchange valid OPENs before the session can proceed.

| Field | Size | Description |
|-------|------|-------------|
| Version | 1 octet | Always 4 for BGP-4 |
| My Autonomous System | 2 octets | Sender's AS number (2-byte; 4-byte AS uses RFC 6793 capability) |
| Hold Time | 2 octets | Proposed hold time in seconds. Must be 0 or ≥ 3. Negotiated to minimum of both peers' values. |
| BGP Identifier | 4 octets | Router ID (highest loopback IP or highest interface IP, vendor-dependent). Must be unique per peer. |
| Optional Parameters | Variable | Capabilities (RFC 5492): MP-BGP, 4-byte AS, route refresh, graceful restart, etc. |

## UPDATE Message

Carries route advertisements and withdrawals in a single message. Minimum length: 23 octets.

### UPDATE Fields

| Field | Size | Description |
|-------|------|-------------|
| Withdrawn Routes Length | 2 octets | Total length of withdrawn routes field (0 if none) |
| Withdrawn Routes | Variable | List of IP prefixes being withdrawn (length + prefix encoding) |
| Total Path Attribute Length | 2 octets | Total length of path attributes field (0 if none) |
| Path Attributes | Variable | Attributes applying to all NLRI in this UPDATE |
| NLRI | Variable | Network Layer Reachability Information — IP prefixes being advertised |

A single UPDATE can simultaneously withdraw old routes and advertise new ones. All NLRI in one UPDATE share the same set of path attributes.

### Prefix Encoding

Each prefix is encoded as: length in bits (1 octet) + prefix padded to octet boundary. Length = 0 means default route (0.0.0.0/0).

## Path Attributes

Every UPDATE containing NLRI must include all well-known mandatory attributes. Attributes are categorized by two independent flags:

| Category | Well-Known | Optional |
|----------|-----------|----------|
| **Mandatory** | Must be recognized and present in every UPDATE with NLRI | — |
| **Discretionary** | Must be recognized but not required in every UPDATE | — |
| **Transitive** | — | Must be forwarded even if not recognized (set Partial bit) |
| **Non-transitive** | — | Must be silently discarded if not recognized |

### Attribute Flag Bits

| Bit | Meaning |
|-----|---------|
| 0 (high) | 0 = well-known, 1 = optional |
| 1 | 0 = non-transitive, 1 = transitive |
| 2 | 0 = complete, 1 = partial (set by router that didn't recognize optional transitive attribute) |
| 3 | 0 = 1-octet length, 1 = 2-octet length (extended) |

### Defined Attributes

| Type Code | Name | Category | Description |
|-----------|------|----------|-------------|
| 1 | ORIGIN | Well-known mandatory | How the route was originated |
| 2 | AS_PATH | Well-known mandatory | Sequence of AS numbers the route has traversed |
| 3 | NEXT_HOP | Well-known mandatory | IP address of next-hop router |
| 4 | MULTI_EXIT_DISC (MED) | Optional non-transitive | Discriminator for multiple exit points to neighbor AS |
| 5 | LOCAL_PREF | Well-known mandatory (iBGP) | Local preference within an AS |
| 6 | ATOMIC_AGGREGATE | Well-known discretionary | Signals that aggregation caused AS_PATH information loss |
| 7 | AGGREGATOR | Optional transitive | AS number and router ID of the aggregating router |

## ORIGIN Attribute

| Value | Name | Meaning |
|-------|------|---------|
| 0 | IGP | Route originated via `network` statement or IGP redistribution within the AS |
| 1 | EGP | Route learned via the legacy EGP protocol |
| 2 | INCOMPLETE | Route learned by other means (redistribution from non-BGP source) |

In the decision process, IGP is preferred over EGP, which is preferred over INCOMPLETE.

## AS_PATH Attribute

Records the sequence of AS numbers a route has traversed. Used for loop detection (discard routes containing own AS) and as a tie-breaker in path selection.

### Segment Types

| Type | Name | Meaning |
|------|------|---------|
| 1 | AS_SET | Unordered set of ASes — used in aggregation when multiple origin ASes exist |
| 2 | AS_SEQUENCE | Ordered list of ASes the route has traversed, most recent first |

### Modification Rules

- **To eBGP peer**: Prepend local AS number to AS_SEQUENCE. If first segment is AS_SET, create new AS_SEQUENCE segment containing local AS.
- **To iBGP peer**: Do not modify AS_PATH.
- **Originating route to eBGP**: Create AS_SEQUENCE containing only local AS.
- **Originating route to iBGP**: Empty AS_PATH (length 0).

**Note**: RFC 4271 defines 2-byte AS numbers. 4-byte AS support (AS 65536+) requires RFC 6793 capability negotiation.

## NEXT_HOP Attribute

Defines the IP address used as the next hop to reach the destinations listed in the UPDATE.

### eBGP Rules
- Default: the IP address of the interface used to establish the BGP session.
- Third-party next hop: if the peer shares a subnet with the NEXT_HOP address, the original next hop may be preserved (avoids extra hop).

### iBGP Rules
- Default: NEXT_HOP is **not modified** when propagating to iBGP peers. The original eBGP next hop is preserved.
- This means iBGP peers must have a route to the eBGP next-hop address (typically via IGP). If the next hop is unreachable, the route is unusable.
- `next-hop-self`: A common vendor configuration that overrides the default and sets NEXT_HOP to the advertising router's own address. Not defined in the RFC but universally implemented.

## LOCAL_PREF and MED

### LOCAL_PREF (Type 5)

- **Scope**: iBGP only. Must NOT be sent to eBGP peers. Must be ignored if received from eBGP peers.
- **Higher value = more preferred**.
- Used to influence outbound traffic within an AS. For example, setting LOCAL_PREF 200 on routes from ISP-A and 100 on routes from ISP-B causes all routers in the AS to prefer ISP-A.
- Default value: 100 (vendor convention, not in RFC).

### MULTI_EXIT_DISC / MED (Type 4)

- **Scope**: Sent to eBGP peers to indicate preference among multiple entry points. Propagated to iBGP peers but NOT re-advertised to other eBGP neighbors.
- **Lower value = more preferred**.
- Optional non-transitive: a receiving AS is not required to honor it.
- Compared only between routes from the **same neighboring AS** (unless `always-compare-med` is configured).
- Default value when absent: vendor-dependent (some treat as 0, others as maximum).

## ATOMIC_AGGREGATE and AGGREGATOR

### ATOMIC_AGGREGATE (Type 6)

When a router aggregates routes and the resulting AS_PATH is less specific (loses information due to AS_SET creation or omission), it attaches ATOMIC_AGGREGATE to signal that the path information may be incomplete. Downstream routers must not de-aggregate (advertise more-specific prefixes) if this attribute is present.

### AGGREGATOR (Type 7)

Optionally attached during aggregation. Contains the AS number and BGP identifier of the router that performed the aggregation. Informational — does not affect path selection.

## Decision Process (Best Path Selection)

When multiple paths exist to the same destination, BGP selects a single best path using the following tie-breaking order. The process stops as soon as a step produces a single winner.

| Step | Criterion | Prefer |
|------|-----------|--------|
| 1 | Highest LOCAL_PREF | Higher value wins |
| 2 | Shortest AS_PATH length | Fewer AS hops (AS_SET counts as 1 regardless of size) |
| 3 | Lowest ORIGIN value | IGP (0) > EGP (1) > INCOMPLETE (2) |
| 4 | Lowest MED | Lower metric wins. Compared only between routes from same neighbor AS. |
| 5 | eBGP over iBGP | Prefer externally learned routes over internally learned |
| 6 | Lowest IGP metric to NEXT_HOP | Closest exit point (hot-potato routing) |
| 7 | Oldest route | Prefer the route that has been in the table longest (stability). Implementation-specific. |
| 8 | Lowest BGP Router ID of advertising peer | Tie-breaker among routes from different peers |
| 9 | Lowest peer IP address | Final tie-breaker when same peer advertises via multiple sessions |

Steps 7–9 are implementation-specific refinements not all mandated by RFC 4271. The RFC defines steps 1–6 as the core algorithm; vendors extend with additional tie-breakers.

## NOTIFICATION Error Codes

A NOTIFICATION message signals a fatal error. The session is closed immediately after sending.

| Code | Name | Subcodes |
|------|------|----------|
| 1 | Message Header Error | 1=Connection Not Synchronized, 2=Bad Message Length, 3=Bad Message Type |
| 2 | OPEN Message Error | 1=Unsupported Version, 2=Bad Peer AS, 3=Bad BGP Identifier, 4=Unsupported Optional Parameter, 6=Unacceptable Hold Time |
| 3 | UPDATE Message Error | 1=Malformed Attribute List, 2=Unrecognized Well-Known Attribute, 3=Missing Well-Known Attribute, 4=Attribute Flags Error, 5=Attribute Length Error, 6=Invalid ORIGIN, 8=Invalid NEXT_HOP, 9=Optional Attribute Error, 10=Invalid Network Field, 11=Malformed AS_PATH |
| 4 | Hold Timer Expired | (no subcodes) |
| 5 | Finite State Machine Error | (no subcodes) |
| 6 | Cease | (no subcodes — used for administrative shutdown, peer deconfigured, etc.) |

## Timers

| Timer | Suggested Default | Description |
|-------|-------------------|-------------|
| ConnectRetryTime | 120 seconds | Time between TCP connection attempts |
| Hold Time | 90 seconds | Maximum interval between KEEPALIVE/UPDATE messages. Negotiated to minimum of both peers' values. 0 disables keepalive. |
| KeepaliveTime | 30 seconds | Interval between KEEPALIVE messages. Recommended: 1/3 of negotiated hold time. |
| MinRouteAdvertisementInterval (MRAI) | 30 s (eBGP), 5 s (iBGP) | Minimum time between UPDATE messages for the same destination to the same peer. Rate-limits convergence. |

Hold time of 0 means keepalives are disabled — used only in special cases (e.g., BFD-protected sessions). If negotiated hold time < 3 seconds, the session is rejected.

## RIB Structure

BGP maintains three conceptual routing tables per address family:

| RIB | Purpose |
|-----|---------|
| **Adj-RIB-In** | Unprocessed routes received from each peer. One per peer. Import policy applied here. |
| **Loc-RIB** | Best routes selected by the decision process. Installed into the global routing table. |
| **Adj-RIB-Out** | Routes selected for advertisement to each peer. One per peer. Export policy applied here. |

Route withdrawal occurs when: (a) the prefix appears in an UPDATE's Withdrawn Routes field, (b) a new UPDATE replaces the prefix with different attributes, or (c) the BGP session is closed (all routes from that peer are implicitly withdrawn).

## Route Preference

Administrative distance (AD) is a vendor implementation concept, not defined in RFC 4271. The values below are widely used conventions (Cisco IOS defaults):

| Route Source | Typical AD |
|-------------|-----------|
| Connected | 0 |
| Static | 1 |
| eBGP | 20 |
| EIGRP (internal) | 90 |
| OSPF | 110 |
| IS-IS | 115 |
| EIGRP (external) | 170 |
| iBGP | 200 |

eBGP routes have a much lower AD than iBGP because externally learned paths are considered more trustworthy (they have been validated by the neighboring AS).

## Key RFCs

- **RFC 4271**: BGP-4 specification (FSM, message formats, path attributes, decision process)
- **RFC 4760**: Multiprotocol Extensions for BGP-4 (MP_REACH_NLRI, MP_UNREACH_NLRI, AFI/SAFI)
- **RFC 6793**: BGP Support for 4-Octet AS Number Space (AS numbers > 65535)
- **RFC 4456**: BGP Route Reflection (eliminates full iBGP mesh requirement)
- **RFC 5065**: BGP Confederations (alternative to route reflection for scaling iBGP)
- **RFC 1997**: BGP Communities Attribute (16-bit tag for route policy)
- **RFC 4360**: BGP Extended Communities (64-bit tags, used in MPLS VPNs)
- **RFC 5492**: Capabilities Advertisement with BGP-4 (optional parameters in OPEN)
- **RFC 8326**: Graceful BGP Session Shutdown (GRACEFUL_SHUTDOWN community)
