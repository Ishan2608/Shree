"""
rag_engine.py — ChromaDB vector store for uploaded documents.

Design:
  - ChromaDB client and SentenceTransformer embedding model are loaded LAZILY —
    only on the first call to index_document() or query_documents().
    This means they do NOT consume RAM at startup if the user never uploads a file.
  - One global in-memory ChromaDB client shared across the process lifetime.
  - index_document()  : chunk + embed + store a parsed document.
  - query_documents() : embed a query and return top-k matching chunks.

The collection is keyed by doc_id (usually the file's UUID prefix) so
re-indexing the same file is idempotent — duplicate chunk IDs are skipped
by ChromaDB's upsert semantics.
"""

# ── Lazy singletons (None until first use) ────────────────────────────────────
_chroma_client = None
_embed_fn       = None
COLLECTION_NAME = "session_documents"


def _get_client():
    """Return the ChromaDB client, creating it on first call."""
    global _chroma_client
    if _chroma_client is None:
        import chromadb
        _chroma_client = chromadb.Client()
    return _chroma_client


def _get_embed_fn():
    """Return the SentenceTransformer embedding function, loading model on first call."""
    global _embed_fn
    if _embed_fn is None:
        from chromadb.utils import embedding_functions
        _embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
    return _embed_fn


# ── Chunking ──────────────────────────────────────────────────────────────────

def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> list[str]:
    """Split a long string into overlapping fixed-size chunks."""
    chunks = []
    start  = 0
    while start < len(text):
        chunks.append(text[start : start + chunk_size])
        start += chunk_size - overlap
    return chunks


# ── Indexing ──────────────────────────────────────────────────────────────────

def index_document(doc_id: str, parsed_data: dict) -> None:
    """
    Chunk and embed a parsed document into ChromaDB.

    ChromaDB client and embedding model are loaded here on first call.

    Args:
        doc_id      : Stable unique identifier (e.g. UUID prefix). Used to
                      namespace chunk IDs so re-indexing is idempotent.
        parsed_data : Dict returned by doc_parser.parse_uploaded_file().
                      Expected keys: type, content.
    """
    if parsed_data.get("type") == "error" or not parsed_data.get("content"):
        return

    collection = _get_client().get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=_get_embed_fn(),
    )

    doc_type    = parsed_data["type"]
    raw_content = parsed_data["content"]
    text_chunks: list[str] = []

    if doc_type in ("xlsx", "csv") and isinstance(raw_content, dict):
        for sheet_name, rows in raw_content.items():
            for row in rows:
                cells = [
                    str(cell).strip()
                    for cell in row
                    if cell is not None and str(cell).strip()
                ]
                if cells:
                    text_chunks.append(f"[Sheet: {sheet_name}] " + " | ".join(cells))
    elif isinstance(raw_content, str):
        text_chunks = chunk_text(raw_content)

    if not text_chunks:
        return

    chunk_ids = [f"{doc_id}_chunk_{i}" for i in range(len(text_chunks))]
    metadatas = [{"source": doc_id, "type": doc_type} for _ in text_chunks]

    collection.upsert(
        documents=text_chunks,
        metadatas=metadatas,
        ids=chunk_ids,
    )


# ── Querying ──────────────────────────────────────────────────────────────────

def query_documents(query: str, n_results: int = 5) -> list[str]:
    """
    Search the vector store for chunks most relevant to query.

    Args:
        query     : Natural-language question.
        n_results : Maximum number of chunks to return.

    Returns:
        List of matching text chunks, best match first.
        Empty list if the collection doesn't exist yet or no results found.
    """
    try:
        collection = _get_client().get_collection(
            name=COLLECTION_NAME,
            embedding_function=_get_embed_fn(),
        )
        results = collection.query(
            query_texts=[query],
            n_results=n_results,
        )
        if results and results.get("documents") and results["documents"][0]:
            return results["documents"][0]
        return []
    except ValueError:
        # Collection does not exist yet — no documents indexed
        return []
    except Exception:
        return []
