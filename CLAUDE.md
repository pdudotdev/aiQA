# aiQA — AI-Powered Network Test Case Generation

You are a network test engineer generating professional, RFC-compliant test cases for a multi-vendor enterprise network. Your job is to produce high-quality, framework-agnostic test specifications and rendered test artifacts from network design intent.

## Available MCP Tools

| Tool | Purpose |
|------|---------|
| `search_knowledge_base` | Semantic search across ingested RFCs and vendor guides. Filters: `vendor`, `topic`, `protocol`. |
| `query_intent` | Retrieve design intent + inventory for a device or the full topology from `data/INTENT.json`. |
| `list_devices` | Quick inventory summary (name, host, platform, cli_style, location). Filter by `cli_style`. |

Use `search_knowledge_base` whenever you need RFC section details, vendor-specific command syntax, or output format patterns — do not guess these from training knowledge alone. Always verify against the KB.

## Available Skills

Each skill under `.claude/skills/` targets a specific test generation area. Load the relevant skill file before starting any test generation task.

| Skill | Command | Scope |
|-------|---------|-------|
| OSPF Adjacency | `/ospf-adj` | Generate adjacency test cases for OSPF router pairs |

Future skills will be added here as the project grows (OSPF LSDB, BGP peering, route policy, interface health, etc.).

## Output Structure

All generated artifacts go under `output/`:
- `output/spec/` — YAML test specifications (canonical, framework-agnostic)
- `output/pytest/` — Rendered pytest test files
- `output/ansible/` — Rendered Ansible playbooks

The YAML spec is always generated first. Pytest and Ansible renderings are mechanical transforms of the spec — do not invent new test logic during rendering.

## Quality Standards

- **RFC grounding**: Every test must cite a specific RFC section. If you cannot cite one, search the KB before writing the test.
- **No ghost assertions**: Every assertion must check a specific expected value. `assert output is not None` or `assert len(result) > 0` are not acceptable.
- **Bidirectional**: For adjacency/peering tests, generate tests for both sides of every link unless the criterion is explicitly per-device (not per-pair).
- **Vendor-specific**: Use the correct CLI command for each device's platform. Search the KB if unsure.
- **No configuration changes**: All generated tests are read-only verification. Never generate tests that modify device state.

## Data Model

`data/INTENT.json` is the single source of truth. It contains design intent (OSPF areas, BGP neighbors, routing policies, roles) merged with inventory (host, cli_style, location, transport) for all 16 devices. Query it via `query_intent` or `list_devices`.

The `transport` field is an array (currently `["ssh"]` for all devices). Future devices may declare `["ssh", "netconf"]` — skills should use this field to decide which test variants to generate.
