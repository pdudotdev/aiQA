# RAG Retrieval Precision Degradation at Scale

## Problem Statement

As the aiQA document corpus grows (adding BGP, EIGRP, STP, and other protocols), **retrieval precision degrades** — the proportion of truly relevant chunks in the top-k results decreases, even though recall (finding *some* relevant result) may remain acceptable.

This is not a latency problem. It is a **relevance quality** problem: imprecise RAG means the agent may retrieve the wrong vendor's CLI command or cite an irrelevant RFC section, producing incorrect assertions in the generated test spec.

## Current Architecture (v1.0)

| Component | Value |
|-----------|-------|
| Chunks | ~170 |
| Collection | `network_kb` |
| Embedding model | `all-MiniLM-L6-v2` (384 dimensions) |
| Chunk size | 800 characters, 100 overlap |
| Splitter | `RecursiveCharacterTextSplitter` (header-aware) |
| Similarity | Cosine distance via ChromaDB HNSW index |
| Metadata filters | `vendor`, `topic`, `source`, `protocol` |
| Contextual headers | Enabled — `[Source: filename | Protocol: protocol]` prepended to each chunk |
| Default top-k | 5 (range 1-10) |

At this scale, retrieval works well. The vector space is sparse enough that queries land near relevant chunks with high confidence. The `protocol` metadata field and contextual headers are already in place to maintain precision as the corpus grows.

## Why Precision Degrades With Scale

### 1. Vector Space Density
More chunks compete for the same top-k slots. A query about "OSPF area types" starts pulling in chunks about "BGP route filtering" or "EIGRP feasibility condition" because the embedding model places them in nearby vector regions — they share networking vocabulary and similar sentence structures.

### 2. Semantic Overlap Between Protocols
Networking concepts share heavy lexical overlap: "neighbor adjacency" appears in OSPF, BGP, and EIGRP docs. "Redistribution," "route summarization," "administrative distance" — all cross-protocol terms. The lightweight `all-MiniLM-L6-v2` model (384 dims, general-purpose training) lacks the representational capacity to cleanly separate these domains.

### 3. Precision vs. Recall Divergence
At 75 chunks, 5/5 results may be relevant. At 750 chunks, perhaps 2-3/5 are. At 7,500, it could be 1/5 or worse — the rest are "close but wrong protocol." Recall stays high but precision drops.

### 4. Metadata Filtering Gaps
Current `vendor` and `topic` filters narrow the search space, but `protocol` filtering is needed to prevent cross-protocol contamination as more protocols are added.

## Optimizations

### Tier 1: Low Effort, High Impact

#### 1. Add a `protocol` Metadata Field — Implemented (v1.0)
Every chunk is tagged with its protocol (`ospf`, `bgp`, `eigrp`, etc.) during ingestion. Filter on it at query time:
```python
where = {"$and": [{"protocol": "ospf"}, {"vendor": "cisco_ios"}]}
```
Protocol is detected from filenames: RFCs via `_RFC_PROTOCOL_MAP`, vendor docs via the third filename segment (e.g., `vendor_cisco_ios_bgp.md` → `bgp`). This eliminates cross-protocol noise immediately.

#### 2. Per-Protocol Collections
Instead of one monolithic collection, create `ospf_kb`, `bgp_kb`, `eigrp_kb`, etc. ChromaDB supports multiple collections natively. This provides **hard isolation** — a BGP query literally cannot return OSPF chunks. Trade-off: slightly more complex ingestion and collection management, but retrieval precision is guaranteed at the collection boundary.

#### 3. Increase Embedding Dimensionality
Replace `all-MiniLM-L6-v2` (384d) with a larger model when the corpus grows:

| Model | Dimensions | Notes |
|-------|-----------|-------|
| `all-mpnet-base-v2` | 768 | 2x capacity, still local/CPU |
| `BAAI/bge-base-en-v1.5` | 768 | Strong on technical text |
| `nomic-embed-text-v1.5` | 768 | Matryoshka embeddings, tunable dim vs. speed |

Higher dimensionality encodes finer-grained semantic distinctions (e.g., "OSPF neighbor adjacency" vs. "BGP neighbor adjacency").

### Tier 2: Medium Effort, Significant Impact

#### 4. Two-Stage Retrieval with Cross-Encoder Re-Ranking
- **Stage 1:** Coarse retrieval — fetch top-20 candidates with loose filtering (bi-encoder / cosine similarity, as today).
- **Stage 2:** Re-rank with a cross-encoder (e.g., `cross-encoder/ms-marco-MiniLM-L-6-v2`) that scores query-chunk relevance jointly.

Cross-encoders see query and chunk *together*, making them far more precise than bi-encoders. Too slow for full-corpus search — hence the two-stage pipeline.

#### 5. Contextual Chunk Headers — Implemented (v1.0)
Each chunk has a context header prepended during ingestion:
```
[Source: rfc2328_summary.md | Protocol: ospf]
The stub flag prevents external LSAs...
```
This gives the embedding model more signal for vector placement without changing the model itself. Source and protocol metadata are prepended to every chunk in `ingest.py`.

#### 6. Hybrid Search (Vector + Keyword)
Network terminology is precise (LSA Type 7, NSSA, eBGP multihop). Keyword matching can outperform semantic similarity for exact terms.

**Option A — ChromaDB `where_document`:**
```python
results = vs.similarity_search(
    query, k=10,
    filter={"protocol": "ospf"},
    where_document={"$contains": "NSSA"}
)
```

**Option B — BM25 + vector fusion:**
Implement reciprocal rank fusion (RRF) combining BM25 keyword scores with cosine similarity scores for true hybrid retrieval.

### Tier 3: Higher Effort, Future-Proofing

#### 7. Agentic Retrieval (Query Decomposition)
Decompose complex test generation queries into targeted sub-queries:
- Skill: *"Generate OSPF adjacency tests for D1C↔C1J (Cisco IOS ↔ Juniper JunOS)"*
- Sub-queries:
  - `"OSPF neighbor show command cisco_ios"` (vendor command lookup)
  - `"OSPF neighbor show command juniper_junos"` (vendor command lookup)
  - `"OSPF adjacency requirements RFC 2328 area stub timer mtu"` (RFC section lookup)

Each sub-query hits a narrower, more precise region of the vector space.

#### 8. Domain-Adapted Embeddings (Fine-Tuning)
Fine-tune the embedding model on networking text. Generate training pairs from the KB:
- **Positive:** (query about OSPF stub areas, chunk from RFC 2328 section 3.6)
- **Negative:** (query about OSPF stub areas, chunk about BGP communities)

This teaches the model that "stub" in OSPF context and "stub" in BGP context are semantically distant. Sentence-transformers supports this via `SentenceTransformer.fit()`.

#### 9. Dynamic Chunk Sizing by Document Type
One-size-fits-all (800 chars) becomes suboptimal as document diversity grows:

| Document Type | Recommended Chunk Size | Rationale |
|---------------|----------------------|-----------|
| RFCs | 400-600 chars | Dense technical prose, smaller = more specific |
| Vendor guides | 600-800 chars | CLI examples need surrounding context |
| Intent | Per-device | Structured; one chunk per router's full config |

---

# Context Window and Token Cost Optimizations

## Problem Statement

Each `/qa` run loads multiple files into the agent's context window. At v1.0, this included a full 24 KB INTENT.json dump (even for 2-device scoped requests), a combined 14.5 KB spec-format.md loaded upfront before any generation, plus the SKILL.md and CLAUDE.md. For a scoped 2-device run on Sonnet 4.6 (~$3/M input tokens), total input overhead was ~65-75K tokens (~$0.20-0.40 per run).

Context bloat has two costs: money and reasoning quality. The agent's effective attention is finite — large irrelevant chunks compete with the content that actually matters for the current step.

## Current Architecture (v2.0)

| File | Loaded when | Size |
|------|------------|------|
| `CLAUDE.md` | Always (Claude Code auto-loads) | 3.5 KB |
| `SKILL.md` | At `/qa` invocation | 12 KB |
| `spec-schema.md` | Step 7, just before YAML generation | 4 KB |
| `spec-renderers.md` | Step 9, just before pytest/Ansible rendering | 5.3 KB |
| `INTENT.json` (scoped) | Step 2, per-device queries only | ~0.6–2 KB per device |
| KB chunks | Steps 4, returned by `search_knowledge_base` | ~10–20 KB |

## Optimizations Implemented (v2.0)

### 1. Scoped Intent Queries

**Before**: `query_intent()` with no argument every run — dumps all 16 devices (~24 KB) into context regardless of request scope.

**After**: When device names are explicit in the request, the skill calls `query_intent("<device>")` per named device. Full topology fetch is reserved for "all devices" or role-based requests.

**Impact**: 2-device scoped run drops from ~24 KB to ~2.4 KB intent input. **-90% for scoped runs.**

### 2. Split spec-format.md into schema + renderers

**Before**: Single 14.5 KB `spec-format.md` loaded at Step 7 (before YAML generation). The renderer guidance (pytest `try/finally` patterns, Ansible `block/always` YAML) was in context during generation — irrelevant noise at that stage.

**After**: Split into:
- `spec-schema.md` (4 KB) — loaded at Step 7, contains only the YAML field definitions and tier 2 schema rules
- `spec-renderers.md` (5.3 KB) — loaded at Step 9, contains only pytest and Ansible patterns

The renderer code examples are not in context when the agent is doing the hardest reasoning (deriving criteria, grounding in RFCs, writing the YAML spec). They arrive only when doing mechanical template work.

**Impact**: -5.2 KB through deduplication and tightening. More importantly, renderer noise is absent during spec generation — the step where hallucination risk is highest.

### 3. Step sequencing (lazy loading)

The skill workflow now explicitly gates each file read to the step that needs it. No file is loaded "just in case." This is enforced by the step instructions ("Do not load spec-renderers.md yet — that's for Steps 9-10").

## Savings Summary

| Scenario | Before (v1.0) | After (v2.0) | Delta |
|----------|:-------------:|:------------:|:-----:|
| Scoped 2-device run — intent | ~24 KB | ~2.4 KB | **-90%** |
| Spec file loaded at generation step | 14.5 KB | 4 KB | **-72%** |
| Total spec + intent overhead | ~38.5 KB | ~11.7 KB | **-70%** |
| Estimated cost (Sonnet 4.6, 2-device) | ~$0.08–0.12 | ~$0.03–0.05 | **~-60%** |

Full topology runs (`/qa ... for all devices`) still fetch the complete INTENT.json — that's unavoidable and correct.

## Recommended Next Steps

| Priority | Optimization | Expected Impact |
|----------|-------------|----------------|
| 1 | **SKILL.md compression** — the 12 KB skill has verbose step templates; tighten code examples | -3–4 KB |
| 2 | **Per-device intent caching** — if multiple steps query the same device, cache the result in-session rather than re-fetching | Latency, not cost |
| 3 | **Streaming spec generation** — write spec entries as they are derived rather than accumulating all in context first | Reduces peak context usage |

---

## Recommended Implementation Order

| Priority | Optimization | Status |
|----------|-------------|--------|
| 1 | `protocol` metadata field | **Implemented** (v1.0) |
| 2 | Contextual chunk headers | **Implemented** (v1.0) |
| 3 | Per-protocol collections | Planned — clean architectural boundary, simple to reason about |
| 4 | Hybrid search (BM25 + vector) | Planned — network terminology is precise; keyword matching helps |
| 5 | Cross-encoder re-ranking | Planned — biggest precision gain for ambiguous queries |
| 6 | Larger embedding model | Planned — when corpus exceeds ~500 chunks |
| 7 | Dynamic chunk sizing | Planned — when adding non-prose document types |
| 8 | Query decomposition | Planned — when multi-criterion generation queries become complex |
| 9 | Fine-tuned embeddings | Planned — when general-purpose models plateau on domain-specific queries |
