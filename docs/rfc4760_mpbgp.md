# Multiprotocol BGP Reference (RFC 4760 — Multiprotocol Extensions for BGP-4)

## Purpose

Base BGP-4 (RFC 4271) is IPv4-specific: the NEXT_HOP attribute carries an IPv4 address, and NLRI in UPDATE messages encodes IPv4 prefixes. RFC 4760 extends BGP to carry routing information for any network layer protocol — IPv6, MPLS VPNs, L2VPN, multicast, and others — by introducing two new path attributes and a capability negotiation mechanism.

The key insight: only two things needed to be added to BGP-4: (a) the ability to associate a Network Layer protocol with next-hop information, and (b) the ability to associate a Network Layer protocol with NLRI. This is achieved through Address Family Identifiers (AFI) and Subsequent Address Family Identifiers (SAFI).

## MP_REACH_NLRI Attribute (Type Code 14)

Used to advertise feasible routes for non-IPv4 address families (or IPv4 with non-unicast SAFI).

- **Category**: Optional non-transitive
- **Carried in**: UPDATE messages (replaces the NLRI and NEXT_HOP fields for non-IPv4 families)

### Format

| Field | Size | Description |
|-------|------|-------------|
| AFI | 2 octets | Address Family Identifier — identifies the network layer protocol |
| SAFI | 1 octet | Subsequent Address Family Identifier — provides additional information about the NLRI type |
| Next Hop Length | 1 octet | Length of next-hop address in octets |
| Next Hop Address | Variable | Network address of the next hop (format depends on AFI). For IPv6: 16 octets (global) or 32 octets (global + link-local). |
| Reserved | 1 octet | Must be set to 0 on transmit, ignored on receipt |
| NLRI | Variable | One or more prefixes being advertised (length + prefix encoding) |

An UPDATE with MP_REACH_NLRI must still carry ORIGIN and AS_PATH attributes. iBGP exchanges also require LOCAL_PREF. The legacy NEXT_HOP attribute (type 3) should NOT be included — it is replaced by the next hop field inside MP_REACH_NLRI.

## MP_UNREACH_NLRI Attribute (Type Code 15)

Used to withdraw previously advertised routes for non-IPv4 address families.

- **Category**: Optional non-transitive
- **Carried in**: UPDATE messages (replaces the Withdrawn Routes field for non-IPv4 families)

### Format

| Field | Size | Description |
|-------|------|-------------|
| AFI | 2 octets | Address Family Identifier |
| SAFI | 1 octet | Subsequent Address Family Identifier |
| Withdrawn Routes | Variable | One or more prefixes being withdrawn (length + prefix encoding) |

An UPDATE carrying only MP_UNREACH_NLRI does not need to include any path attributes.

## Address Family Identifiers (AFI)

AFI values are assigned by IANA. The most commonly used in network deployments:

| AFI | Protocol | Usage |
|-----|----------|-------|
| 1 | IPv4 | Standard IPv4 routing (unicast, multicast, VPNv4) |
| 2 | IPv6 | IPv6 routing (unicast, multicast, VPNv6) |
| 25 | L2VPN | Layer 2 VPN services (VPLS, EVPN) |

## Subsequent Address Family Identifiers (SAFI)

SAFI qualifies the type of NLRI within an address family:

| SAFI | Name | Description |
|------|------|-------------|
| 1 | Unicast | Unicast forwarding (most common: IPv4-unicast, IPv6-unicast) |
| 2 | Multicast | Multicast RPF lookups (separate multicast routing table) |
| 4 | MPLS Labels | NLRI carries MPLS label bindings (RFC 8277) |
| 65 | VPLS | Virtual Private LAN Service (RFC 4761, 6624) |
| 70 | EVPN | Ethernet VPN (RFC 7432) |
| 128 | MPLS VPN | VPNv4/VPNv6 unicast (RFC 4364 — MPLS L3VPN) |
| 129 | MPLS VPN Multicast | VPN multicast (RFC 6514) |

### Common AFI/SAFI Combinations

| AFI/SAFI | Name | Purpose |
|----------|------|---------|
| 1/1 | IPv4 Unicast | Standard IPv4 BGP — the only address family supported without MP-BGP |
| 1/128 | VPNv4 Unicast | MPLS L3VPN IPv4 (routes carry Route Distinguisher + IPv4 prefix) |
| 2/1 | IPv6 Unicast | Standard IPv6 BGP |
| 2/128 | VPNv6 Unicast | MPLS L3VPN IPv6 |
| 25/65 | L2VPN VPLS | Virtual Private LAN Service signaling |
| 25/70 | L2VPN EVPN | Ethernet VPN signaling (modern data center fabric) |

## Capability Advertisement

MP-BGP capabilities are negotiated during session establishment via the OPEN message's Optional Parameters field (RFC 5492).

### Multiprotocol Capability

| Field | Value |
|-------|-------|
| Capability Code | 1 (Multiprotocol Extensions) |
| Capability Length | 4 octets |
| AFI | 2 octets — the address family |
| Reserved | 1 octet — must be 0 |
| SAFI | 1 octet — the sub-address family |

Each supported AFI/SAFI combination is advertised as a separate capability. For bidirectional route exchange, **both peers** must advertise the same AFI/SAFI capability.

Example: A router supporting IPv4-unicast, IPv6-unicast, and VPNv4 includes three capability entries in its OPEN: (AFI=1, SAFI=1), (AFI=2, SAFI=1), (AFI=1, SAFI=128).

## Error Handling

When a BGP speaker receives an UPDATE with a malformed MP_REACH_NLRI or MP_UNREACH_NLRI:

1. **Delete** all routes previously received from that peer for the affected AFI/SAFI.
2. **Ignore** all subsequent routes with that AFI/SAFI for the duration of the session.
3. **Optionally** send a NOTIFICATION (UPDATE Message Error, Optional Attribute Error) and terminate the session.

This approach limits the blast radius — a malformed IPv6 update does not tear down IPv4 routing.

## Backward Compatibility

Both MP_REACH_NLRI and MP_UNREACH_NLRI are **optional non-transitive** attributes. A BGP speaker that does not support MP-BGP will:

- Silently ignore these attributes (not forward them)
- Continue to process standard IPv4 NLRI and NEXT_HOP normally
- Not advertise any multiprotocol capabilities in OPEN

This means MP-BGP and legacy BGP-4 routers can coexist on the same network. IPv4-unicast routing works identically whether or not MP-BGP is supported. Non-IPv4 address families simply require all routers in the path to support the relevant AFI/SAFI.

## Key RFCs

- **RFC 4760**: Multiprotocol Extensions for BGP-4 (MP_REACH_NLRI, MP_UNREACH_NLRI, AFI/SAFI)
- **RFC 4271**: BGP-4 specification (base protocol that MP-BGP extends)
- **RFC 5492**: Capabilities Advertisement with BGP-4 (capability negotiation in OPEN)
- **RFC 2545**: Use of BGP-4 Multiprotocol Extensions for IPv6 Inter-Domain Routing (IPv6 next-hop encoding)
- **RFC 4364**: BGP/MPLS IP Virtual Private Networks (VPNv4, SAFI 128)
- **RFC 7432**: BGP MPLS-Based Ethernet VPN (EVPN, SAFI 70)
