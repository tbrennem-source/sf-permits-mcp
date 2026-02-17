"""OpenAI embedding client with batching.

Uses text-embedding-3-small (1536 dimensions, $0.02/1M tokens).
Batches requests to stay within API limits.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Optional

logger = logging.getLogger(__name__)

_MODEL = "text-embedding-3-small"
_DIMENSIONS = 1536
_BATCH_SIZE = 100  # OpenAI allows up to 2048, but 100 keeps memory reasonable
_MAX_RETRIES = 3


def get_embedding_dimensions() -> int:
    """Return the embedding vector dimensionality."""
    return _DIMENSIONS


def embed_texts(texts: list[str], model: str = _MODEL) -> list[list[float]]:
    """Embed a list of texts using OpenAI API.

    Args:
        texts: List of text strings to embed.
        model: OpenAI model name.

    Returns:
        List of embedding vectors (each a list of floats).

    Raises:
        RuntimeError: If OPENAI_API_KEY is not set.
        Exception: On API failure after retries.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable not set")

    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError("openai package not installed. Run: pip install openai")

    client = OpenAI(api_key=api_key)
    all_embeddings: list[list[float]] = []

    for i in range(0, len(texts), _BATCH_SIZE):
        batch = texts[i : i + _BATCH_SIZE]
        # Truncate very long texts (OpenAI limit is 8191 tokens ≈ 30K chars)
        batch = [t[:30000] if len(t) > 30000 else t for t in batch]

        for attempt in range(_MAX_RETRIES):
            try:
                response = client.embeddings.create(input=batch, model=model)
                batch_embeddings = [item.embedding for item in response.data]
                all_embeddings.extend(batch_embeddings)
                break
            except Exception as e:
                if attempt < _MAX_RETRIES - 1:
                    wait = 2 ** attempt
                    logger.warning("Embedding API error (attempt %d/%d), retrying in %ds: %s",
                                   attempt + 1, _MAX_RETRIES, wait, e)
                    time.sleep(wait)
                else:
                    raise

        if i + _BATCH_SIZE < len(texts):
            logger.info("Embedded %d/%d texts...", min(i + _BATCH_SIZE, len(texts)), len(texts))

    return all_embeddings


def embed_query(text: str, model: str = _MODEL) -> list[float]:
    """Embed a single query text.

    Convenience wrapper around embed_texts for single queries.
    """
    results = embed_texts([text], model=model)
    return results[0]
