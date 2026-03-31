"""Smoke tests for ChromaDB RAG retrieval quality.

Run with: python -m pytest testing/test_retrieval.py -v
Requires: aiqa venv activated, ChromaDB populated (make ingest).
"""
import sys
from pathlib import Path

import pytest
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHROMA_DIR = str(PROJECT_ROOT / "data" / "chroma")
COLLECTION = "network_kb"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"


@pytest.fixture(scope="module")
def vectorstore():
    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
    return Chroma(
        persist_directory=CHROMA_DIR,
        embedding_function=embeddings,
        collection_name=COLLECTION,
    )


def _sources(results):
    """Extract unique source filenames from search results."""
    return {doc.metadata["source"] for doc in results}


def _protocols(results):
    """Extract unique protocols from search results."""
    return {doc.metadata["protocol"] for doc in results}


def _vendors(results):
    """Extract unique vendors from search results."""
    return {doc.metadata["vendor"] for doc in results}


# --- Filter correctness ---


class TestFilterCorrectness:
    """Verify metadata filters enforce strict constraints."""

    def test_protocol_filter_returns_only_matching_protocol(self, vectorstore):
        results = vectorstore.similarity_search(
            "neighbor adjacency state", k=10, filter={"protocol": "ospf"}
        )
        assert len(results) > 0
        assert _protocols(results) == {"ospf"}

    def test_vendor_filter_returns_only_matching_vendor(self, vectorstore):
        results = vectorstore.similarity_search(
            "show ospf neighbor", k=10, filter={"vendor": "cisco_ios"}
        )
        assert len(results) > 0
        assert _vendors(results) == {"cisco_ios"}

    def test_compound_filter_vendor_and_protocol(self, vectorstore):
        results = vectorstore.similarity_search(
            "timer hello dead interval",
            k=5,
            filter={"$and": [{"vendor": "juniper_junos"}, {"protocol": "ospf"}]},
        )
        assert len(results) > 0
        assert _vendors(results) == {"juniper_junos"}
        assert _protocols(results) == {"ospf"}

    def test_topic_rfc_filter(self, vectorstore):
        results = vectorstore.similarity_search(
            "OSPF adjacency requirements", k=5, filter={"topic": "rfc"}
        )
        assert len(results) > 0
        assert all(doc.metadata["topic"] == "rfc" for doc in results)
        assert _vendors(results) == {"all"}

    def test_impossible_filter_returns_empty(self, vectorstore):
        """vendor=cisco_ios + topic=rfc is impossible (RFCs are vendor=all)."""
        results = vectorstore.similarity_search(
            "OSPF configuration",
            k=5,
            filter={"$and": [{"vendor": "cisco_ios"}, {"topic": "rfc"}]},
        )
        assert len(results) == 0

    def test_nonexistent_vendor_protocol_returns_empty(self, vectorstore):
        """VyOS has no EIGRP documentation."""
        results = vectorstore.similarity_search(
            "EIGRP metric",
            k=5,
            filter={"$and": [{"vendor": "vyos"}, {"protocol": "eigrp"}]},
        )
        assert len(results) == 0


# --- Semantic relevance ---


class TestSemanticRelevance:
    """Verify queries return chunks from expected source files."""

    def test_ospf_cisco_returns_cisco_ospf_doc(self, vectorstore):
        results = vectorstore.similarity_search(
            "OSPF hello interval configuration revert",
            k=5,
            filter={"$and": [{"vendor": "cisco_ios"}, {"protocol": "ospf"}]},
        )
        assert "vendor_cisco_ios_ospf.md" in _sources(results)

    def test_bgp_junos_returns_junos_bgp_doc(self, vectorstore):
        results = vectorstore.similarity_search(
            "BGP export policy group neighbor",
            k=5,
            filter={"$and": [{"vendor": "juniper_junos"}, {"protocol": "bgp"}]},
        )
        assert "vendor_juniper_junos_bgp.md" in _sources(results)

    def test_eigrp_returns_cisco_eigrp_doc(self, vectorstore):
        results = vectorstore.similarity_search(
            "EIGRP K-value metric variance",
            k=5,
            filter={"protocol": "eigrp"},
        )
        assert "vendor_cisco_ios_eigrp.md" in _sources(results)

    def test_rfc_ospf_returns_rfc2328(self, vectorstore):
        results = vectorstore.similarity_search(
            "OSPF hello dead timer adjacency state machine",
            k=5,
            filter={"$and": [{"topic": "rfc"}, {"protocol": "ospf"}]},
        )
        assert "rfc2328_summary.md" in _sources(results)

    def test_rfc_bgp_returns_rfc4271(self, vectorstore):
        results = vectorstore.similarity_search(
            "BGP finite state machine OPEN UPDATE NOTIFICATION",
            k=5,
            filter={"$and": [{"topic": "rfc"}, {"protocol": "bgp"}]},
        )
        assert "rfc4271_bgp.md" in _sources(results)

    def test_routeros_bgp_returns_mikrotik_bgp_doc(self, vectorstore):
        results = vectorstore.similarity_search(
            "BGP connection template instance local.role",
            k=5,
            filter={"$and": [{"vendor": "mikrotik_ros"}, {"protocol": "bgp"}]},
        )
        assert "vendor_mikrotik_ros_bgp.md" in _sources(results)


# --- Chunk count sanity ---


class TestChunkCounts:
    """Verify the collection has expected chunk distribution."""

    def test_total_chunk_count(self, vectorstore):
        collection = vectorstore._collection
        count = collection.count()
        assert count >= 500, f"Expected >= 500 chunks, got {count}"
        assert count <= 600, f"Expected <= 600 chunks, got {count}"

    def test_all_protocols_present(self, vectorstore):
        for protocol in ("ospf", "bgp", "eigrp"):
            results = vectorstore.similarity_search(
                "configuration", k=1, filter={"protocol": protocol}
            )
            assert len(results) == 1, f"No chunks found for protocol={protocol}"

    def test_all_vendors_present(self, vectorstore):
        for vendor in ("cisco_ios", "arista_eos", "juniper_junos", "aruba_aoscx", "mikrotik_ros", "vyos"):
            results = vectorstore.similarity_search(
                "configuration", k=1, filter={"vendor": vendor}
            )
            assert len(results) == 1, f"No chunks found for vendor={vendor}"
