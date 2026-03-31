"""Ingest network knowledge base docs into ChromaDB via LangChain."""
import shutil
import sys
from pathlib import Path

from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_text_splitters import RecursiveCharacterTextSplitter

DOCS_DIR = Path(__file__).parent / "docs"
CHROMA_DIR = Path(__file__).parent / "data" / "chroma"
COLLECTION_NAME = "network_kb"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100

_RFC_PROTOCOL_MAP = {
    "rfc2328": "ospf",
    "rfc3101": "ospf",
    "rfc7868": "eigrp",
    "rfc4271": "bgp",
    "rfc4760": "bgp",
}


def extract_metadata(file_path: Path) -> dict:
    """Derive vendor, topic, and protocol metadata from filename."""
    name = file_path.stem
    if name.startswith("vendor_"):
        parts = name[len("vendor_"):].split("_")
        # Convention: vendor_<vendor>_<protocol>.md (e.g. vendor_cisco_ios_bgp.md)
        # Current files: vendor_<vendor>.md (all OSPF)
        vendor = "_".join(parts[:2]) if len(parts) >= 2 else parts[0]
        protocol = parts[2] if len(parts) > 2 else "ospf"
        return {"vendor": vendor, "topic": "vendor_guide", "source": file_path.name, "protocol": protocol}
    elif name.startswith("rfc"):
        rfc_id = name.split("_")[0]
        protocol = _RFC_PROTOCOL_MAP.get(rfc_id, "general")
        return {"vendor": "all", "topic": "rfc", "source": file_path.name, "protocol": protocol}
    return {"vendor": "all", "topic": "general", "source": file_path.name, "protocol": "general"}


def ingest():
    """Load protocol docs, chunk, embed, and store in ChromaDB."""
    md_files = sorted(DOCS_DIR.glob("*.md"))
    if not md_files:
        print(f"No .md files found in {DOCS_DIR}")
        sys.exit(1)

    documents = []
    for fp in md_files:
        try:
            text = fp.read_text(encoding="utf-8")
        except Exception as exc:
            print(f"WARNING: skipping {fp.name}: {exc}")
            continue
        metadata = extract_metadata(fp)
        documents.append(Document(page_content=text, metadata=metadata))
    print(f"Loaded {len(documents)} document(s) from {DOCS_DIR}")

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n## ", "\n### ", "\n\n", "\n", " "],
    )
    chunks = []
    for doc in documents:
        splits = splitter.split_documents([doc])
        for chunk in splits:
            chunk.metadata = doc.metadata.copy()
        chunks.extend(splits)

    # Prepend contextual headers for better embedding quality
    for chunk in chunks:
        src = chunk.metadata.get("source", "unknown")
        proto = chunk.metadata.get("protocol", "general")
        chunk.page_content = f"[Source: {src} | Protocol: {proto}]\n{chunk.page_content}"

    print(f"Split into {len(chunks)} chunk(s)")

    embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)
    Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=str(CHROMA_DIR),
        collection_name=COLLECTION_NAME,
    )
    print(f"Stored in ChromaDB at {CHROMA_DIR}")


if __name__ == "__main__":
    if "--clean" in sys.argv and CHROMA_DIR.exists():
        shutil.rmtree(CHROMA_DIR)
        print(f"Cleaned {CHROMA_DIR}")
    ingest()
