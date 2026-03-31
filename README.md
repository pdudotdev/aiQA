# aiQA • AI-Powered Network Test Case Generation

[![Version](https://img.shields.io/badge/version-1.2-1a1a2e)](https://github.com/pdudotdev/aiQA/releases/tag/v1.2.0)
![License](https://img.shields.io/badge/license-GPLv3-1a1a2e)
[![Last Commit](https://img.shields.io/github/last-commit/pdudotdev/aiQA?color=1a1a2e)](https://github.com/pdudotdev/aiQA/commits/main/)

| | |
|---|---|
| **Platforms** | ![Cisco IOS](https://img.shields.io/badge/Cisco_IOS-0d47a1) ![Cisco IOS-XE](https://img.shields.io/badge/Cisco_IOS--XE-0d47a1) ![Arista EOS](https://img.shields.io/badge/Arista_EOS-0d47a1) ![Juniper JunOS](https://img.shields.io/badge/Juniper_JunOS-0d47a1) ![Aruba AOS](https://img.shields.io/badge/Aruba_AOS-0d47a1) ![Vyatta VyOS](https://img.shields.io/badge/Vyatta_VyOS-0d47a1) ![MikroTik RouterOS](https://img.shields.io/badge/MikroTik_RouterOS-0d47a1) ![FRR](https://img.shields.io/badge/FRR-0d47a1) |
| **Integrations** | ![MCP](https://img.shields.io/badge/MCP-1e88e5) ![ChromaDB](https://img.shields.io/badge/ChromaDB-1e88e5) ![Claude](https://img.shields.io/badge/Claude-1e88e5) |

## Overview

AI-powered network test case generator for multi-vendor networks.

Describe your network intent once. aiQA generates RFC-compliant test cases from it — vendor-specific CLI commands, precise assertions, and full traceability to RFC sections. Output is a framework-agnostic YAML spec rendered into ready-to-run pytest suites and Ansible playbooks.

**Supported models:**
- Haiku 4.5, Sonnet 4.6, Opus 4.6
- Default: Opus 4.6, Effort Low

**Output samples:**
- See [**output_samples**](output_samples/)

**Documentation:**
- [**WORKFLOW.md**](metadata/workflow/WORKFLOW.md)
- [**OPTIMIZATIONS.md**](metadata/scalability/OPTIMIZATIONS.md)

**What's new in v1.2:**
- [**CHANGELOG.md**](CHANGELOG.md)

## Tech Stack

| Technology | Role |
|-----------|------|
| Python | Core language |
| FastMCP | MCP server exposing 3 tools |
| Claude | Reasoning, test design, spec generation |
| LangChain | RAG pipeline (chunking, embedding, retrieval) |
| ChromaDB | Vector database for knowledge base |

## Scope

aiQA uses a single general-purpose `/qa` skill that handles any protocol, any feature, and any test type from a natural language request. No per-protocol skill files needed.

All tests are active: configure a condition → wait → check the result → teardown (revert). Every test modifies device configuration and must have a complete teardown block. The agent warns the user and requires explicit confirmation before generating any tests.

**Supported protocols** (any protocol present in INTENT.json + KB):
- OSPF (RFCs 2328, 3101; 6 vendor implementations)
- BGP (RFC 4271)
- EIGRP, interface health, route policy — derive from KB and intent

## Test Network Topology

**Network diagram:**

![topology](metadata/topology/DBL-TOPOLOGY.png)

**Lab environment:**
- 16 devices defined in [**TOPOLOGY.yml**](TOPOLOGY.yml)
- 5 x Cisco IOS, 3 x Cisco IOS-XE, 4 x Arista cEOS, 2 x MikroTik CHR, 1 x Juniper JunOS, 1 x Aruba AOS-CX
- See [**lab_configs**](lab_configs/) for my test network's configuration

## Installation

**Prerequisites:** Python 3.11+

**Step 1 - Install and ingest:**
```bash
sudo apt install git make python3.12-venv -y
cd ~ && git clone https://github.com/pdudotdev/aiQA
cd aiQA && make setup
```

**Step 2 - Authenticate with Claude:**
```bash
claude auth login
```

**Step 3 - Register the MCP server:**
```bash
claude mcp add aiqa -s user -- /home/<user>/aiQA/aiqa/bin/python /home/<user>/aiQA/server.py
```

## MCP Tools

| Tool | Description |
|------|-------------|
| `search_knowledge_base` | Search network knowledge base (RFCs, vendor guides) with protocol/vendor/topic filters |
| `query_intent` | Retrieve network design intent and inventory from `data/INTENT.json` |
| `list_devices` | List inventory devices, optionally filtered by CLI style |

## Customization

aiQA is designed to work with your own test topology. Bring your own:

| What | Where | Format |
|------|-------|--------|
| **Network intent** | `data/INTENT.json` | JSON: router roles, OSPF areas, links, neighbors, inventory fields |
| **Protocol docs** | `docs/*.md` | Markdown (re-ingest with `make ingest`) |

## QA Workflow

**Generate tests from a natural language request:**
```
claude
> /qa OSPF timer mismatch tests between D1C and C1J
```

The skill:
1. Parses the request — protocol, feature, device scope, failure mode
2. Resolves device intent (scoped per-device queries, not full topology dump)
3. Asks clarifying questions if needed (scope, test condition)
4. Searches the KB for RFC grounding, vendor CLI commands, and rollback patterns
5. Presents a **test plan for confirmation** before generating anything
6. Generates a YAML spec, pytest suite, and Ansible playbook

| Output | Path | Description |
|--------|------|-------------|
| YAML spec | `output/spec/<protocol>_<feature>[_<scope>].yaml` | Canonical, framework-agnostic test specification |
| Pytest suite | `output/pytest/test_<protocol>_<feature>[_<scope>].py` | Executable tests using scrapli for SSH |
| Ansible playbook | `output/ansible/playbook_<protocol>_<feature>[_<scope>].yml` | Ansible tasks using `cli_command` module |
| Emergency rollback | `output/ansible/playbook_<protocol>_<feature>_rollback.yml` | Unconditional teardown playbook |

**Safety model**: Every test has a mandatory `teardown` block. pytest uses `try/finally` (teardown always runs). Ansible uses `block/always`. A session-level rollback registry in `conftest.py` covers interrupted test runs. Cross-vendor pairs test both directions; same-vendor pairs test one direction only.

## Knowledge Base

Protocol documentation lives in `docs/` as Markdown files. Each file is tagged with `vendor`, `topic`, and `protocol` metadata during ingestion.

To update after editing docs:
```bash
make ingest
```

**RAG optimizations in place:**
- `protocol` metadata field — filters search by protocol (ospf, bgp, eigrp), eliminating cross-protocol noise
- Contextual chunk headers — source and protocol prepended to each chunk for better embedding quality
- Compound filtering — combine vendor, topic, and protocol filters in a single query
- Scoped intent queries — `query_intent("<device>")` per named device; full topology only when needed
- Lazy-loaded schema files — `spec-schema.md` at spec generation, `spec-renderers.md` at rendering

See [**OPTIMIZATIONS.md**](metadata/scalability/OPTIMIZATIONS.md) for the full optimization roadmap.

## Project Structure

```
aiQA/
├── server.py                     # FastMCP server (3 tools)
├── ingest.py                     # RAG ingestion pipeline
├── data/
│   ├── INTENT.json               # Network design intent + inventory (16 devices)
│   └── chroma/                   # ChromaDB vector store (generated)
├── docs/                         # Knowledge base (RFCs + vendor guides)
│   ├── rfc2328_summary.md
│   ├── rfc3101_nssa.md
│   └── vendor_*.md               # cisco_ios, arista_eos, juniper_junos, aruba_aoscx, mikrotik_ros, vyos
├── output/
│   ├── spec/                     # Generated YAML test specifications
│   ├── pytest/                   # Generated pytest test files
│   └── ansible/                  # Generated Ansible playbooks
├── metadata/
│   ├── scalability/              # RAG optimization roadmap
│   └── workflow/                 # End-to-end workflow documentation
├── .claude/
│   ├── spec-schema.md            # YAML spec schema — loaded at Step 7, before generation
│   ├── spec-renderers.md         # pytest + Ansible renderer guidance — loaded at Step 9, before rendering
│   └── skills/
│       └── qa/
│           └── SKILL.md          # /qa general QA methodology skill (13-step workflow, QC-1 through QC-8)
├── CLAUDE.md                     # Agent system prompt (tools, quality standards, data model)
├── Makefile                      # Setup automation (make setup / ingest / clean)
├── requirements.txt
└── README.md
```

## Disclaimer

You are responsible for defining your own network inventory and design intent, building your test environment, and meeting the necessary prerequisites (Python 3.11+, Claude CLI/API, network device access).

## License

Licensed under [**GNUv3.0**](LICENSE).

## Collaborations

Interested in collaborating?
- **Email:** [**hello@ainoc.dev**](mailto:hello@ainoc.dev)
- **LinkedIn:** [**LinkedIn**](https://www.linkedin.com/in/tmihaicatalin/)
