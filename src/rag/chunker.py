"""Chunking strategies for different knowledge tiers.

Each chunker returns a list of dicts:
    {"content": str, "source_file": str, "source_section": str, "metadata": dict}
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# --- Chunk size constants ---
MAX_CHUNK_CHARS = 800
OVERLAP_CHARS = 150
MIN_CHUNK_CHARS = 50


def chunk_tier1_json(filepath: Path) -> list[dict]:
    """Chunk a tier1 structured JSON file.

    Strategy: One chunk per top-level key that has meaningful content.
    Includes the key name and any description/aliases as context.
    """
    try:
        with open(filepath) as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.warning("Could not parse %s: %s", filepath.name, e)
        return []

    if isinstance(data, list):
        # Array-type files (e.g., G-20-tables.json)
        chunks = []
        for i, item in enumerate(data):
            text = json.dumps(item, indent=2, default=str)
            if len(text) < MIN_CHUNK_CHARS:
                continue
            chunks.append({
                "content": f"[{filepath.stem}] Item {i}:\n{text}",
                "source_file": filepath.name,
                "source_section": f"item_{i}",
                "metadata": {"tier": "tier1", "type": "structured"},
            })
        return chunks

    chunks = []
    # Extract file-level context
    file_desc = data.get("description") or data.get("source") or filepath.stem
    skip_keys = {"metadata", "meta", "_metadata", "source", "source_url",
                 "source_urls", "last_verified", "description"}

    for key, value in data.items():
        if key in skip_keys:
            continue

        # Build a chunk with context
        if isinstance(value, dict):
            text = _dict_to_text(key, value, file_desc)
        elif isinstance(value, list):
            text = _list_to_text(key, value, file_desc)
        elif isinstance(value, str) and len(value) >= MIN_CHUNK_CHARS:
            text = f"[{file_desc}] {key}: {value}"
        else:
            continue

        if len(text) < MIN_CHUNK_CHARS:
            continue

        # Split oversized chunks
        if len(text) > MAX_CHUNK_CHARS * 2:
            sub_chunks = _split_text(text, MAX_CHUNK_CHARS, OVERLAP_CHARS)
            for j, sub in enumerate(sub_chunks):
                chunks.append({
                    "content": sub,
                    "source_file": filepath.name,
                    "source_section": f"{key}[{j}]",
                    "metadata": {"tier": "tier1", "type": "structured"},
                })
        else:
            chunks.append({
                "content": text,
                "source_file": filepath.name,
                "source_section": key,
                "metadata": {"tier": "tier1", "type": "structured"},
            })

    return chunks


def chunk_raw_text(text: str, source_file: str,
                   max_chars: int = MAX_CHUNK_CHARS,
                   overlap: int = OVERLAP_CHARS) -> list[dict]:
    """Chunk raw text (tier2 info sheets, tier3 ABs) with paragraph-boundary snapping.

    Strategy: Sliding window with preference for splitting at paragraph boundaries.
    """
    if not text or len(text.strip()) < MIN_CHUNK_CHARS:
        return []

    paragraphs = re.split(r'\n\s*\n', text)
    chunks = []
    current = ""
    section = "body"

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # Detect section headers
        header_match = re.match(r'^(#{1,3}\s+.+|[A-Z][A-Z\s]{5,}$|Section\s+\d+)', para)
        if header_match:
            section = para[:60].strip()

        if len(current) + len(para) + 2 <= max_chars:
            current = f"{current}\n\n{para}" if current else para
        else:
            if current and len(current) >= MIN_CHUNK_CHARS:
                chunks.append({
                    "content": current.strip(),
                    "source_file": source_file,
                    "source_section": section,
                    "metadata": {"tier": _infer_tier(source_file), "type": "raw_text"},
                })
            # Start new chunk with overlap from end of previous
            if current and overlap > 0:
                overlap_text = current[-overlap:]
                current = f"{overlap_text}\n\n{para}"
            else:
                current = para

    # Don't forget the last chunk
    if current and len(current.strip()) >= MIN_CHUNK_CHARS:
        chunks.append({
            "content": current.strip(),
            "source_file": source_file,
            "source_section": section,
            "metadata": {"tier": _infer_tier(source_file), "type": "raw_text"},
        })

    return chunks


def chunk_code_sections(text: str, source_file: str) -> list[dict]:
    """Chunk legal code text (tier4) by section boundaries.

    Strategy: Split at section/article headers. Keep sections together
    up to max_chars, then split further if needed.
    """
    if not text or len(text.strip()) < MIN_CHUNK_CHARS:
        return []

    # Common section patterns in SF codes
    section_pattern = re.compile(
        r'^(?:'
        r'(?:SECTION|Section|SEC\.?)\s+\d+[A-Z]?[\.\d]*'
        r'|ARTICLE\s+\d+'
        r'|CHAPTER\s+\d+'
        r'|AB-\d+'
        r'|Table\s+\d+[A-Z]?[-\.]'
        r')',
        re.MULTILINE
    )

    # Split text at section boundaries
    splits = list(section_pattern.finditer(text))

    if not splits:
        # No section headers found — fall back to paragraph chunking
        return chunk_raw_text(text, source_file)

    chunks = []
    for i, match in enumerate(splits):
        start = match.start()
        end = splits[i + 1].start() if i + 1 < len(splits) else len(text)
        section_text = text[start:end].strip()

        if len(section_text) < MIN_CHUNK_CHARS:
            continue

        section_name = match.group(0).strip()[:80]

        if len(section_text) <= MAX_CHUNK_CHARS * 2:
            chunks.append({
                "content": section_text,
                "source_file": source_file,
                "source_section": section_name,
                "metadata": {"tier": "tier4", "type": "code_section"},
            })
        else:
            # Split large sections further
            sub_chunks = _split_text(section_text, MAX_CHUNK_CHARS, OVERLAP_CHARS)
            for j, sub in enumerate(sub_chunks):
                chunks.append({
                    "content": sub,
                    "source_file": source_file,
                    "source_section": f"{section_name}[{j}]",
                    "metadata": {"tier": "tier4", "type": "code_section"},
                })

    return chunks


# --- Helpers ---

def _dict_to_text(key: str, d: dict, context: str) -> str:
    """Convert a dict to readable text for embedding."""
    lines = [f"[{context}] {key}:"]
    for k, v in d.items():
        if isinstance(v, (list, dict)):
            v_str = json.dumps(v, default=str)
            if len(v_str) > 300:
                v_str = v_str[:297] + "..."
        else:
            v_str = str(v)
        lines.append(f"  {k}: {v_str}")
    return "\n".join(lines)


def _list_to_text(key: str, items: list, context: str) -> str:
    """Convert a list to readable text for embedding."""
    lines = [f"[{context}] {key}:"]
    for item in items[:20]:  # Cap at 20 items per chunk
        if isinstance(item, dict):
            lines.append(f"  - {json.dumps(item, default=str)[:200]}")
        else:
            lines.append(f"  - {str(item)[:200]}")
    if len(items) > 20:
        lines.append(f"  ... and {len(items) - 20} more items")
    return "\n".join(lines)


def _split_text(text: str, max_chars: int, overlap: int) -> list[str]:
    """Split text into chunks with overlap, preferring sentence boundaries."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + max_chars
        if end >= len(text):
            chunks.append(text[start:])
            break
        # Try to break at sentence boundary
        for boundary in [". ", ".\n", "\n\n", "\n", " "]:
            pos = text.rfind(boundary, start + max_chars // 2, end)
            if pos > start:
                end = pos + len(boundary)
                break
        chunks.append(text[start:end].strip())
        start = end - overlap
    return [c for c in chunks if len(c) >= MIN_CHUNK_CHARS]


def _infer_tier(source_file: str) -> str:
    """Infer the tier from the source file path."""
    if "tier1" in source_file:
        return "tier1"
    elif "tier2" in source_file:
        return "tier2"
    elif "tier3" in source_file or "AB-" in source_file:
        return "tier3"
    elif "tier4" in source_file:
        return "tier4"
    return "unknown"
