"""pgvector store for knowledge chunks.

Handles table creation, upsert, and vector similarity search
against the existing Railway PostgreSQL database.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# SQL constants
TABLE = "knowledge_chunks"

CREATE_EXTENSION = "CREATE EXTENSION IF NOT EXISTS vector"

CREATE_TABLE = f"""
CREATE TABLE IF NOT EXISTS {TABLE} (
    id SERIAL PRIMARY KEY,
    embedding vector(1536),
    content TEXT NOT NULL,
    source_tier TEXT NOT NULL DEFAULT 'official',
    source_file TEXT,
    source_section TEXT,
    trust_weight FLOAT DEFAULT 1.0,
    chunk_index INTEGER,
    metadata JSONB DEFAULT '{{}}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_confirmed_at TIMESTAMPTZ
)
"""

CREATE_INDEX = f"""
CREATE INDEX IF NOT EXISTS idx_chunks_embedding
ON {TABLE} USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100)
"""

CREATE_INDEX_TIER = f"""
CREATE INDEX IF NOT EXISTS idx_chunks_source_tier ON {TABLE} (source_tier)
"""

CREATE_INDEX_FILE = f"""
CREATE INDEX IF NOT EXISTS idx_chunks_source_file ON {TABLE} (source_file)
"""


def _get_conn():
    """Get a psycopg2 connection to the database."""
    import psycopg2
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL not set")
    return psycopg2.connect(url, connect_timeout=10)


def ensure_table():
    """Create the knowledge_chunks table and indexes if they don't exist."""
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(CREATE_EXTENSION)
        cur.execute(CREATE_TABLE)
        # ivfflat index needs rows to exist; create after first insert
        cur.execute(CREATE_INDEX_TIER)
        cur.execute(CREATE_INDEX_FILE)
        conn.commit()
        logger.info("knowledge_chunks table ensured")
    finally:
        conn.close()


def insert_chunks(chunks: list[dict], embeddings: list[list[float]],
                  source_tier: str = "official", trust_weight: float = 1.0):
    """Bulk insert chunks with their embeddings.

    Args:
        chunks: List of chunk dicts from chunker (content, source_file, source_section, metadata).
        embeddings: Corresponding embedding vectors.
        source_tier: 'official', 'amy', or 'learned'.
        trust_weight: Trust score for reranking.
    """
    if len(chunks) != len(embeddings):
        raise ValueError(f"Chunk count ({len(chunks)}) != embedding count ({len(embeddings)})")

    conn = _get_conn()
    try:
        cur = conn.cursor()
        for i, (chunk, emb) in enumerate(zip(chunks, embeddings)):
            cur.execute(
                f"INSERT INTO {TABLE} "
                "(embedding, content, source_tier, source_file, source_section, "
                "trust_weight, chunk_index, metadata) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    str(emb),  # pgvector accepts string representation
                    chunk["content"].replace('\x00', '').replace('\ufffd', ''),
                    source_tier,
                    chunk.get("source_file"),
                    chunk.get("source_section"),
                    trust_weight,
                    i,
                    json.dumps(chunk.get("metadata", {})),
                ),
            )
        conn.commit()
        logger.info("Inserted %d chunks (tier=%s)", len(chunks), source_tier)
    finally:
        conn.close()


def clear_tier(source_tier: str = "official"):
    """Delete all chunks for a given tier (for re-ingestion)."""
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(f"DELETE FROM {TABLE} WHERE source_tier = %s", (source_tier,))
        deleted = cur.rowcount
        conn.commit()
        logger.info("Deleted %d chunks (tier=%s)", deleted, source_tier)
        return deleted
    finally:
        conn.close()


def clear_file(source_file: str):
    """Delete all chunks for a specific source file."""
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(f"DELETE FROM {TABLE} WHERE source_file = %s", (source_file,))
        deleted = cur.rowcount
        conn.commit()
        return deleted
    finally:
        conn.close()


def search(query_embedding: list[float], top_k: int = 20,
           source_tier: Optional[str] = None) -> list[dict]:
    """Vector similarity search.

    Args:
        query_embedding: Query vector (1536 dims).
        top_k: Number of results to return.
        source_tier: Optional filter by tier.

    Returns:
        List of dicts with: content, source_file, source_section, source_tier,
        trust_weight, similarity, metadata.
    """
    conn = _get_conn()
    try:
        cur = conn.cursor()
        tier_clause = "AND source_tier = %s" if source_tier else ""
        params = [str(query_embedding), top_k]
        if source_tier:
            params = [str(query_embedding), source_tier, top_k]
            query = (
                f"SELECT content, source_file, source_section, source_tier, "
                f"trust_weight, 1 - (embedding <=> %s) AS similarity, metadata "
                f"FROM {TABLE} "
                f"WHERE source_tier = %s "
                f"ORDER BY embedding <=> %s "
                f"LIMIT %s"
            )
            params = [str(query_embedding), source_tier,
                      str(query_embedding), top_k]
        else:
            query = (
                f"SELECT content, source_file, source_section, source_tier, "
                f"trust_weight, 1 - (embedding <=> %s) AS similarity, metadata "
                f"FROM {TABLE} "
                f"ORDER BY embedding <=> %s "
                f"LIMIT %s"
            )
            params = [str(query_embedding), str(query_embedding), top_k]

        cur.execute(query, params)
        rows = cur.fetchall()

        results = []
        for row in rows:
            meta = row[6]
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except json.JSONDecodeError:
                    meta = {}
            results.append({
                "content": row[0],
                "source_file": row[1],
                "source_section": row[2],
                "source_tier": row[3],
                "trust_weight": row[4],
                "similarity": float(row[5]),
                "metadata": meta,
            })
        return results
    finally:
        conn.close()


def get_stats() -> dict:
    """Get chunk count statistics."""
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT source_tier, COUNT(*) FROM {TABLE} GROUP BY source_tier")
        tier_counts = dict(cur.fetchall())
        cur.execute(f"SELECT COUNT(*) FROM {TABLE}")
        total = cur.fetchone()[0]
        cur.execute(
            f"SELECT source_file, COUNT(*) FROM {TABLE} "
            f"GROUP BY source_file ORDER BY COUNT(*) DESC LIMIT 20"
        )
        top_files = dict(cur.fetchall())
        return {
            "total_chunks": total,
            "by_tier": tier_counts,
            "top_files": top_files,
        }
    finally:
        conn.close()


def insert_single_note(text: str, metadata: dict) -> int:
    """Insert a single expert note into the knowledge base.

    Embeds the text, then inserts as an 'amy'-tier chunk with high trust weight.

    Args:
        text: The note content.
        metadata: Dict with added_by_user_id, firm_id, query_context, etc.

    Returns:
        Number of chunks inserted (1 on success).
    """
    from datetime import datetime, timezone
    from src.rag.embeddings import embed_texts

    emb = embed_texts([text])[0]
    metadata["added_at"] = datetime.now(timezone.utc).isoformat()

    chunks = [{
        "content": text,
        "source_file": "expert-note",
        "source_section": metadata.get("query_context", "")[:100],
        "metadata": metadata,
    }]
    insert_chunks(chunks, [emb], source_tier="amy", trust_weight=0.9)
    return 1


def rebuild_ivfflat_index():
    """Rebuild the IVFFlat index after bulk insertion.

    Should be called after large batch inserts for optimal search performance.
    """
    conn = _get_conn()
    try:
        cur = conn.cursor()
        cur.execute(f"DROP INDEX IF EXISTS idx_chunks_embedding")
        cur.execute(CREATE_INDEX)
        conn.commit()
        logger.info("IVFFlat index rebuilt")
    finally:
        conn.close()
