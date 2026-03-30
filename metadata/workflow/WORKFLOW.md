# aiQA — How It Works

aiQA is a framework that gives Claude the context it needs to generate professional, RFC-compliant network test cases from design intent. It produces vendor-agnostic YAML test specifications and renders them into executable pytest suites and Ansible playbooks.

---

## The Tools

aiQA exposes 3 tools registered in `server.py`:

| Tool | Purpose | Backend |
|------|---------|---------|
| `search_knowledge_base` | Semantic search over RFCs and vendor docs | ChromaDB + MiniLM embeddings |
| `query_intent` | Network design intent (roles, OSPF areas, links, router IDs) | `data/INTENT.json` |
| `list_devices` | Inventory summary filtered by CLI style | `data/INTENT.json` |

### The Knowledge Base

`search_knowledge_base` performs RAG (Retrieval-Augmented Generation):

1. **Ingestion** (one-time, via `make ingest`): Markdown files from `docs/` are chunked, embedded with `all-MiniLM-L6-v2`, and stored in ChromaDB with metadata (`vendor`, `topic`, `source`, `protocol`). Each chunk gets a contextual header prepended (`[Source: filename | Protocol: protocol]`) for better embedding quality.
2. **Query**: The search query is embedded into the same vector space. ChromaDB returns the top-k most similar chunks by cosine distance.
3. **Filters**: Optional `vendor`, `topic`, and `protocol` filters narrow results before similarity search. Compound filtering is supported (e.g., `vendor=cisco_ios` + `protocol=ospf`).

Device inventory and design intent are NOT in ChromaDB — they are served at query time by `list_devices` and `query_intent`.

See [OPTIMIZATIONS.md](../scalability/OPTIMIZATIONS.md) for the full RAG optimization roadmap.

---

## Test Generation Flow

The agent is a Claude Code session with the aiQA MCP server active. The user invokes a skill to start test generation.

### Example: `/ospf-adj D1C C1J`

```
/ospf-adj D1C C1J

  Step 0 — Preflight
    list_devices()         → verify inventory is loaded
    query_intent()         → verify 16 routers available
    search_knowledge_base() → verify KB responds

  Step 1 — Load Spec Format
    Read .claude/spec-format.md
    → YAML schema, pytest renderer guidance, Ansible renderer guidance

  Step 2 — Extract Pairs
    query_intent()         → full topology from INTENT.json
    → filter OSPF routers (have igp.ospf)
    → enumerate P2P pairs from direct_links
    → determine area + area_type per pair (handle ABR dual-area)
    → filter to pairs where D1C or C1J is an endpoint
    → present pair table → user confirms

  Step 3 — Research
    search_knowledge_base(vendor=cisco_ios, protocol=ospf)
    search_knowledge_base(vendor=juniper_junos, protocol=ospf)
    → retrieve vendor CLI commands for each criterion
    → retrieve RFC section references for each criterion

  Step 4 — Generate YAML Spec
    → apply 9 criteria to each pair (ADJ-01..ADJ-09)
    → populate query.ssh_cli from RAG results (vendor-specific)
    → populate assertion schema from criteria table (type, field, expected, match_by)
    → write output/spec/ospf_adjacency_C1J_D1C.yaml

  Step 5 — Render Pytest
    → transform spec entries into parametrized pytest functions
    → write output/pytest/test_ospf_adjacency_C1J_D1C.py + conftest.py

  Step 6 — Render Ansible
    → transform spec entries into one task per test entry
    → write output/ansible/playbook_ospf_adjacency_C1J_D1C.yml + inventory.yml

  Step 7 — Summary
    → report test count, breakdown by criterion
```

---

## Output Pipeline

The three-stage output pipeline ensures the YAML spec is the canonical source — renderers are mechanical transforms, not independent test logic.

```
data/INTENT.json
      │
      ▼
  YAML Spec                    ← canonical, framework-agnostic
  output/spec/
      │
      ├──► Pytest Suite         ← scrapli SSH, parametrized from spec
      │    output/pytest/
      │
      └──► Ansible Playbook     ← cli_command module, tasks from spec
           output/ansible/
```

### YAML Spec

Every test entry in the spec contains:
- `id` — stable, sortable test identifier
- `criterion` — which ADJ-XX (or future protocol criterion) applies
- `rfc` — mandatory RFC section citation
- `device` + `peer` — full inventory fields (host, platform, cli_style, interface)
- `query.ssh_cli` — the exact vendor-specific show command
- `assertion` — type, field, expected value, match_by (no ghost assertions)
- `context` — topology fields (area, area_type)

### Pytest Renderer

- Uses `scrapli` for SSH connections (platform mapped from `cli_style`)
- `conftest.py` provides session-scoped connection fixtures parametrized by device
- Each test sends `query.ssh_cli`, parses output, locates the correct row via `match_by`, asserts `field == expected`
- Run with: `pytest output/pytest/ --junitxml=output/pytest/results.xml`

### Ansible Renderer

- Uses `ansible.netcommon.cli_command` (generic) or platform-specific modules
- One task per test entry: sends the CLI command, asserts the expected value
- Task names include criterion ID and description for traceability
- `vars.rfc` annotation per task for audit trail

---

## Scoped vs Full-Topology Runs

| Invocation | What it generates | Output filename suffix |
|------------|-------------------|----------------------|
| `/ospf-adj` | All OSPF adjacency pairs in topology | *(none)* |
| `/ospf-adj D1C` | Only pairs where D1C is an endpoint | `_D1C` |
| `/ospf-adj D1C C1J` | Pairs where D1C **or** C1J is an endpoint | `_C1J_D1C` |

Device names in the suffix are sorted alphabetically so the filename is canonical regardless of argument order.

---

## Adding a New Skill

Each skill under `.claude/skills/<name>/` is self-contained. Adding a new protocol test category (e.g., BGP peering) requires no changes to `CLAUDE.md`, `server.py`, or `spec-format.md`.

Steps:
1. Create `.claude/skills/<name>/SKILL.md` — workflow, criteria table + assertion schemas, data extraction algorithm
2. Add any new RFC or vendor docs to `docs/`
3. Run `make ingest` to rebuild the KB
4. Register the skill in the `Available Skills` table in `CLAUDE.md`

The `spec-format.md` YAML schema is extensible — add new `context` fields for the new protocol without breaking existing skills.

---

## Customization

| What | Where | How |
|------|-------|-----|
| Network intent + inventory | `data/INTENT.json` | Edit directly; one JSON object per router with roles, links, IGP config, and inventory fields |
| Protocol docs | `docs/*.md` | Add Markdown files; run `make ingest` to rebuild ChromaDB |
| New skill | `.claude/skills/<name>/SKILL.md` | Create with criteria table + workflow; no server changes needed |
