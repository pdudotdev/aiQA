"""aiQA MCP Server — network KB search + design intent + inventory tools."""
import json
import logging
import threading
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator
from fastmcp import FastMCP

logging.basicConfig(level=logging.INFO, format="%(name)s: %(message)s")
log = logging.getLogger("aiqa")

_PROJECT_ROOT = Path(__file__).resolve().parent
_CHROMA_DIR = str(_PROJECT_ROOT / "data" / "chroma")
_COLLECTION = "network_kb"
_EMBEDDING_MODEL = "all-MiniLM-L6-v2"
_INTENT_JSON = _PROJECT_ROOT / "data" / "INTENT.json"

# --- Pydantic input models ---

class BaseParamsModel(BaseModel):
    @model_validator(mode='before')
    @classmethod
    def parse_string_input(cls, v):
        if isinstance(v, str):
            import json as _json
            try:
                obj, _ = _json.JSONDecoder().raw_decode(v.strip())
                return obj
            except (ValueError, _json.JSONDecodeError) as e:
                raise ValueError(f"Could not parse params as JSON: {v!r}") from e
        return v


class KBQuery(BaseParamsModel):
    query: str = Field(..., description="Search question for the network knowledge base", max_length=500)
    vendor: Literal["cisco_ios", "arista_eos", "juniper_junos", "aruba_aoscx", "mikrotik_ros", "vyos"] | None = Field(
        None, description="Filter by vendor"
    )
    topic: Literal["rfc", "vendor_guide"] | None = Field(None, description="Filter by topic: rfc | vendor_guide")
    protocol: Literal["ospf", "bgp", "eigrp"] | None = Field(None, description="Filter by protocol: ospf | bgp | eigrp")
    top_k: int = Field(5, description="Number of results to return (1-10)", ge=1, le=10)


class IntentQuery(BaseParamsModel):
    device: str | None = Field(None, description="Device name to filter intent (omit for full topology)")


class DeviceListQuery(BaseParamsModel):
    cli_style: str | None = Field(
        None, description="Filter by CLI style: ios | eos | junos | aos | routeros | vyos"
    )


# --- RAG lazy init ---

_embeddings = None
_vectorstore = None
_init_lock = threading.Lock()


def _get_vectorstore():
    global _embeddings, _vectorstore
    if _vectorstore is None:
        with _init_lock:
            if _vectorstore is None:
                from langchain_huggingface import HuggingFaceEmbeddings
                from langchain_chroma import Chroma
                _embeddings = HuggingFaceEmbeddings(model_name=_EMBEDDING_MODEL)
                _vectorstore = Chroma(
                    persist_directory=_CHROMA_DIR,
                    embedding_function=_embeddings,
                    collection_name=_COLLECTION,
                )
    return _vectorstore


# --- Intent helpers ---

def _load_intent() -> dict | None:
    if _INTENT_JSON.exists():
        try:
            return json.loads(_INTENT_JSON.read_text())
        except Exception as exc:
            log.warning("Failed to load INTENT.json: %s", exc)
    return None


# --- MCP server ---

mcp = FastMCP("aiqa")


@mcp.tool(name="search_knowledge_base")
async def search_knowledge_base(params: KBQuery) -> dict:
    """Search the network knowledge base for relevant RFC or vendor documentation.

    Returns ranked document chunks. Use filters to narrow results:
    - vendor: cisco_ios, arista_eos, juniper_junos, aruba_aoscx, mikrotik_ros, vyos
    - topic: rfc, vendor_guide
    - protocol: ospf, bgp, eigrp
    """
    import asyncio

    where = {}
    if params.vendor:
        where["vendor"] = params.vendor
    if params.topic:
        where["topic"] = params.topic
    if params.protocol:
        where["protocol"] = params.protocol

    if len(where) > 1:
        where = {"$and": [{k: v} for k, v in where.items()]}

    search_kwargs = {"k": params.top_k}
    if where:
        search_kwargs["filter"] = where

    def _sync_search():
        vs = _get_vectorstore()
        return vs.similarity_search(params.query, **search_kwargs)

    try:
        results = await asyncio.to_thread(_sync_search)
    except Exception as exc:
        log.error("KB search failed: %s", exc)
        return {"error": f"Knowledge base unavailable: {exc}"}

    return {
        "results": [
            {"content": doc.page_content, "metadata": doc.metadata}
            for doc in results
        ]
    }


@mcp.tool(name="query_intent")
async def query_intent(params: IntentQuery) -> dict:
    """Retrieve network design intent for a device or the full topology.

    Returns OSPF/BGP config, roles, direct links, loopbacks, and inventory
    fields (host, cli_style, location, transport) from data/INTENT.json.

    Omit device to return intent for all devices.
    """
    import asyncio

    intent = await asyncio.to_thread(_load_intent)
    if not intent:
        return {"error": "Intent unavailable — run ingest or check data/INTENT.json"}

    if params.device is None:
        return intent

    routers = intent.get("routers", {})
    if params.device not in routers:
        known = ", ".join(sorted(routers)) or "(none)"
        return {"error": f"Unknown device {params.device!r} — known: {known}"}

    return {"device": params.device, "intent": routers[params.device]}


@mcp.tool(name="list_devices")
async def list_devices(params: DeviceListQuery) -> dict:
    """Return a concise inventory summary — name, host, platform, cli_style, location.

    Pass cli_style to filter by vendor family (e.g. 'eos', 'ios', 'junos').
    """
    import asyncio

    intent = await asyncio.to_thread(_load_intent)
    if not intent:
        return {"error": "Inventory unavailable — check data/INTENT.json"}

    routers = intent.get("routers", {})
    if not routers:
        return {"error": "No devices found in INTENT.json"}

    inventory_fields = ("host", "platform", "cli_style", "location", "transport", "vrf")
    devices = {}
    for name, data in routers.items():
        entry = {k: data.get(k) for k in inventory_fields}
        if params.cli_style and entry.get("cli_style") != params.cli_style:
            continue
        devices[name] = entry

    if not devices:
        return {"error": f"No devices found with cli_style={params.cli_style!r}"}

    return {"devices": devices}


if __name__ == "__main__":
    mcp.run()
