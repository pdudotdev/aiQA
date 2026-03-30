# Changelog

## v1.0 — 2026-03-30

Initial release.

### MCP Server (`server.py`)

- 3 tools: `search_knowledge_base`, `query_intent`, `list_devices`
- Pydantic-validated inputs with typed enums for vendor, topic, protocol, cli_style
- Lazy-init ChromaDB with thread-safe singleton
- Compound metadata filtering (`$and` for multi-field queries)

### RAG Pipeline (`ingest.py`)

- 8 knowledge base documents: 2 RFCs (2328, 3101) + 6 vendor guides (Cisco IOS, Arista EOS, Juniper JunOS, Aruba AOS-CX, MikroTik RouterOS, VyOS)
- `all-MiniLM-L6-v2` embeddings (384 dimensions), ChromaDB HNSW index
- Metadata: `vendor`, `topic`, `source`, `protocol` — auto-derived from filenames
- Contextual chunk headers prepended for embedding quality
- `RecursiveCharacterTextSplitter` with Markdown header separators (800 chars, 100 overlap)

### Network Intent (`data/INTENT.json`)

- 16 devices across 4 autonomous systems
- 11 OSPF routers (4 leaf, 2 ABR, 2 core, 1 DC, 2 edge), 19 adjacency pairs
- 2 EIGRP-only routers, 3 BGP-only routers
- 6 platforms: Cisco IOS-XE, Arista EOS, Juniper JunOS, Aruba AOS-CX, MikroTik RouterOS, VyOS (FRR)
- Dual-area ABRs (D1C, D2B) with `area_types` dict; leaf routers with `area_type` string

### Skill: `/ospf-adj`

- 8-step workflow: preflight, spec format load, pair extraction, KB research, YAML spec generation, pytest render, Ansible render, summary
- 8 test criteria (ADJ-01 through ADJ-08): Interface Up, Neighbor Presence, State FULL, Area ID Match, Timer Match, Stub Agreement, MTU Match, Router ID Unique
- Scoped output: 1 device = OR (all pairs for that device), 2+ devices = AND (pairs between listed devices only)
- Canonical filenames with sorted device suffix
- cli_style to KB vendor mapping table for accurate RAG queries
- Per-device test ID pattern for ADJ-08; pair-based for all others
- 6 quality controls (QC-1 through QC-6) enforced during generation

### Shared Schema (`spec-format.md`)

- YAML test spec schema with device, peer, context, query, assertion fields
- 8 assertion types: interface_up, neighbor_presence, neighbor_state, timer_match, area_match, stub_agreement, mtu_match, router_id_unique
- Pytest renderer guidance: scrapli platform mapping, session-scoped fixtures, JUnit XML output
- Ansible renderer guidance: `cli_command` module, `ansible_network_os` mapping, RFC traceability via `vars.rfc`

### Output Structure

- `output/spec/` — canonical YAML test specifications
- `output/pytest/` — scrapli-based pytest suites with `conftest.py`
- `output/ansible/` — Ansible playbooks with `inventory.yml`

### Documentation

- `CLAUDE.md` — agent system prompt (tools, quality standards, data model)
- `metadata/workflow/WORKFLOW.md` — end-to-end test generation flow
- `metadata/scalability/OPTIMIZATIONS.md` — RAG precision roadmap (9 optimizations, 2 implemented)
- `testing/test_scenarios.md` — 10 manual test scenarios with expected pair/test counts

### Infrastructure

- `Makefile` with `setup`, `install`, `ingest`, `clean` targets
- Python 3.11+ venv (`aiqa/`)
- CPU-only PyTorch for local embeddings
