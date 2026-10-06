from __future__ import annotations

import re
from pathlib import Path

from django.conf import settings

COLLECTION_NAME = "hr_policies"


def chunk_markdown(path: Path) -> list[dict]:
    raw = path.read_text(encoding="utf-8")
    lines = raw.splitlines()
    document = path.stem.replace("-", " ").title()
    section = document
    buffer: list[str] = []
    chunks: list[dict] = []

    def flush() -> None:
        body = "\n".join(buffer).strip()
        if not body:
            return
        chunks.append(
            {
                "id": f"{path.stem}-{len(chunks)}",
                "document": document,
                "section": section,
                "source": path.name,
                "text": f"{document}\nSection: {section}\n\n{body}",
            }
        )

    for line in lines:
        heading = re.match(r"^#{1,3}\s+(.*\S)\s*$", line)
        if heading:
            flush()
            buffer = []
            title = heading.group(1).strip()
            if line.startswith("# "):
                document = title
                section = title
            else:
                section = title
            continue
        buffer.append(line)
    flush()
    return chunks


def index_policies(policies_dir: Path | None = None, persist_dir: Path | None = None) -> int:
    policies_dir = policies_dir or settings.POLICIES_DIR
    collection = _recreate_collection(persist_dir)
    chunks: list[dict] = []
    for path in sorted(policies_dir.glob("*.md")):
        chunks.extend(chunk_markdown(path))
    if not chunks:
        return 0
    collection.upsert(
        ids=[chunk["id"] for chunk in chunks],
        documents=[chunk["text"] for chunk in chunks],
        metadatas=[
            {
                "document": chunk["document"],
                "section": chunk["section"],
                "source": chunk["source"],
            }
            for chunk in chunks
        ],
    )
    return len(chunks)


def search_policies(query: str, k: int = 4, persist_dir: Path | None = None) -> dict:
    try:
        collection = _open_collection(persist_dir)
    except Exception:
        return {
            "matches": [],
            "error": "The policy index is empty. Run python manage.py index_policies.",
        }
    count = collection.count()
    if count == 0:
        return {
            "matches": [],
            "error": "The policy index is empty. Run python manage.py index_policies.",
        }
    result = collection.query(
        query_texts=[query],
        n_results=min(k, count),
        include=["documents", "metadatas", "distances"],
    )
    matches = []
    documents = (result.get("documents") or [[]])[0]
    metadatas = (result.get("metadatas") or [[]])[0]
    distances = (result.get("distances") or [[]])[0]
    for document, metadata, distance in zip(documents, metadatas, distances):
        metadata = metadata or {}
        matches.append(
            {
                "document": metadata.get("document", ""),
                "section": metadata.get("section", ""),
                "source": metadata.get("source", ""),
                "distance": round(float(distance), 3),
                "excerpt": (document or "")[:900],
            }
        )
    return {"query": query, "matches": matches}


def _client(persist_dir: Path | None):
    import chromadb
    from chromadb.config import Settings

    path = persist_dir or settings.CHROMA_DIR
    path.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(
        path=str(path),
        settings=Settings(anonymized_telemetry=False),
    )


def _recreate_collection(persist_dir: Path | None):
    client = _client(persist_dir)
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def _open_collection(persist_dir: Path | None):
    return _client(persist_dir).get_collection(COLLECTION_NAME)


def release_vector_store() -> None:
    """Close Chroma so Windows can delete the index files."""
    try:
        from chromadb.api.shared_system_client import SharedSystemClient
    except Exception:
        return
    systems = list(getattr(SharedSystemClient, "_identifier_to_system", {}).values())
    for system in systems:
        try:
            system.stop()
        except Exception:
            pass
    try:
        SharedSystemClient.clear_system_cache()
    except Exception:
        pass
