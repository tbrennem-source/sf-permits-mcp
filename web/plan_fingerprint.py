"""Document fingerprinting for plan analysis jobs (Phase D2).

Three-layer identity matching per SPEC-analysis-history-phases-d-f.md:

  Layer 1 — Content hash:  SHA-256 of raw PDF bytes (exact match = same file)
  Layer 2 — Structural:    (page_number, sheet_number) composite pairs
                            extracted from vision page_extractions
  Layer 3 — Metadata:      property_address OR permit_number OR normalised filename

This module handles:
  - SHA-256 computation (Phase 1 — at upload)
  - Structural fingerprint extraction (Phase 2 — after vision processing)
  - Overlap scoring between two fingerprints
  - Same-user job lookup for linking

Non-behaviors (from spec):
  - Must NOT block upload if SHA-256 fails — silent skip, pdf_hash_failed=TRUE
  - Must NOT fingerprint hollow sessions (len(extractions)==0)
  - Must NOT use sheet_number as sole key — always (page_number, sheet_number)
  - Must NOT link jobs across different user accounts
"""

import hashlib
import json
import logging
import math
import re

logger = logging.getLogger(__name__)

# Fingerprint overlap threshold for auto-linking (60% matching pairs)
OVERLAP_THRESHOLD = 0.60


# ── Layer 1: SHA-256 content hash ────────────────────────────────


def compute_pdf_hash(pdf_bytes: bytes) -> str | None:
    """Compute SHA-256 hex digest of PDF bytes.

    Returns:
        Hex string, or None on failure (caller should set pdf_hash_failed=TRUE).
    """
    try:
        return hashlib.sha256(pdf_bytes).hexdigest()
    except Exception as e:
        logger.warning("pdf_hash computation failed: %s", e)
        return None


# ── Layer 2: Structural fingerprint ──────────────────────────────


def extract_structural_fingerprint(page_extractions: list[dict]) -> list[dict]:
    """Extract (page_number, sheet_number) composite pairs from vision results.

    Guard: returns [] if len(extractions)==0 (hollow session).

    Each pair has:
      - page_number: int (1-based, from vision extraction)
      - sheet_number: str | None  (e.g. "A1.1"; None if not found)

    Args:
        page_extractions: List of dicts from analyze_plans() vision results.

    Returns:
        List of {"page_number": int, "sheet_number": str|None} dicts, sorted
        by page_number.  Empty list for hollow sessions.
    """
    if not page_extractions:
        return []

    pairs = []
    for ext in page_extractions:
        page_num = ext.get("page_number")
        if page_num is None:
            continue
        sheet_num = _extract_sheet_number(ext)
        pairs.append({"page_number": int(page_num), "sheet_number": sheet_num})

    pairs.sort(key=lambda p: p["page_number"])
    return pairs


def _extract_sheet_number(ext: dict) -> str | None:
    """Extract sheet number from a page extraction dict.

    Looks for X#.# pattern (e.g. A1.1, S2.0, M3.2) in common fields.
    Returns None if not found — these pages are still included in the
    fingerprint but with lower weight during overlap scoring.
    """
    # Direct fields first
    for field in ("sheet_number", "sheet_id", "drawing_number", "sheet"):
        val = ext.get(field)
        if val and isinstance(val, str):
            m = re.search(r"\b[A-Za-z]\d+\.\d+\b", val)
            if m:
                return m.group(0).upper()

    # Scan title and notes as fallback
    for field in ("title", "notes", "description"):
        val = ext.get(field)
        if val and isinstance(val, str):
            m = re.search(r"\b[A-Za-z]\d+\.\d+\b", val)
            if m:
                return m.group(0).upper()

    return None


# ── Overlap scoring ───────────────────────────────────────────────


def compute_overlap_score(
    fp_a: list[dict],
    fp_b: list[dict],
) -> float:
    """Compute overlap score between two structural fingerprints.

    Formula (from spec):
        matching_pairs / total_unique_pairs_across_both

    Weighting:
        - Pairs with sheet_number present: weight 1.0
        - Pairs with sheet_number=None:    weight 0.5

    A pair matches when both page_number AND sheet_number are equal.
    For None sheet numbers, match on page_number alone (both must be None).

    Args:
        fp_a, fp_b: Lists of {"page_number", "sheet_number"} dicts.

    Returns:
        Float in [0.0, 1.0].  Returns 0.0 if either fingerprint is empty.
    """
    if not fp_a or not fp_b:
        return 0.0

    def _key(p: dict) -> tuple:
        return (p["page_number"], p["sheet_number"])

    def _weight(p: dict) -> float:
        return 1.0 if p["sheet_number"] is not None else 0.5

    set_a = {_key(p): _weight(p) for p in fp_a}
    set_b = {_key(p): _weight(p) for p in fp_b}

    all_keys = set(set_a) | set(set_b)
    if not all_keys:
        return 0.0

    matched_weight = sum(
        min(set_a[k], set_b[k]) for k in all_keys if k in set_a and k in set_b
    )
    total_weight = sum(max(set_a.get(k, 0.0), set_b.get(k, 0.0)) for k in all_keys)

    if total_weight == 0.0:
        return 0.0
    return matched_weight / total_weight


def fingerprints_match(fp_a: list[dict], fp_b: list[dict]) -> bool:
    """Return True if overlap score meets the 60% threshold."""
    return compute_overlap_score(fp_a, fp_b) >= OVERLAP_THRESHOLD


# ── Layer 3: Metadata matching ────────────────────────────────────


def _normalize_filename(filename: str) -> str:
    """Lowercase, strip extension, collapse whitespace/punctuation."""
    name = filename.lower()
    # Strip .pdf extension
    if name.endswith(".pdf"):
        name = name[:-4]
    # Collapse non-alphanumeric runs to single space
    name = re.sub(r"[^a-z0-9]+", " ", name).strip()
    return name


def metadata_matches(job_a: dict, job_b: dict) -> bool:
    """Return True if two jobs share a meaningful metadata signal.

    Checks (in priority order):
      1. Same permit_number (non-null)
      2. Same property_address (case-insensitive)
      3. Same normalised filename
    """
    # 1. Permit number
    pn_a = (job_a.get("permit_number") or "").strip()
    pn_b = (job_b.get("permit_number") or "").strip()
    if pn_a and pn_b and pn_a.upper() == pn_b.upper():
        return True

    # 2. Property address
    addr_a = (job_a.get("property_address") or "").strip()
    addr_b = (job_b.get("property_address") or "").strip()
    if addr_a and addr_b and addr_a.upper() == addr_b.upper():
        return True

    # 3. Normalised filename
    fn_a = _normalize_filename(job_a.get("filename") or "")
    fn_b = _normalize_filename(job_b.get("filename") or "")
    if fn_a and fn_b and fn_a == fn_b:
        return True

    return False


# ── Candidate lookup ──────────────────────────────────────────────


def find_candidate_jobs(
    *,
    user_id: int,
    exclude_job_id: str,
    pdf_hash: str | None,
    filename: str,
    property_address: str | None,
    permit_number: str | None,
    limit: int = 20,
) -> list[dict]:
    """Find same-user jobs that are candidate matches for fingerprinting.

    Returns completed jobs for the same user, ordered newest first,
    excluding the current job.  Deliberately broad — overlap scoring
    narrows the field in Phase 2.

    Layer 1 (exact hash) and Layer 3 (metadata) candidates are returned.
    Caller does Layer 2 (structural overlap) scoring on the result.
    """
    from src.db import query

    # Build OR conditions for Layer 1 + Layer 3
    conditions = ["user_id = %s", "job_id != %s", "status = 'completed'"]
    params: list = [user_id, exclude_job_id]

    layer_conditions = []

    # Layer 1: same content hash
    if pdf_hash:
        layer_conditions.append("pdf_hash = %s")
        params.append(pdf_hash)

    # Layer 3: permit_number match
    if permit_number:
        layer_conditions.append("UPPER(permit_number) = UPPER(%s)")
        params.append(permit_number)

    # Layer 3: property_address match
    if property_address:
        layer_conditions.append("UPPER(property_address) = UPPER(%s)")
        params.append(property_address)

    # Layer 3: normalised filename — do client-side since SQL normalisation
    # is complex; just pull recent jobs and filter in Python
    # (limit is small enough that this is fine)

    if layer_conditions:
        conditions.append("(" + " OR ".join(layer_conditions) + ")")

    where = " AND ".join(conditions)
    params.append(limit)

    try:
        rows = query(
            "SELECT job_id, filename, property_address, permit_number, "
            "pdf_hash, structural_fingerprint "
            f"FROM plan_analysis_jobs WHERE {where} "
            "ORDER BY created_at DESC LIMIT %s",
            tuple(params),
        )
    except Exception:
        logger.debug("find_candidate_jobs failed", exc_info=True)
        return []

    return [
        {
            "job_id": r[0],
            "filename": r[1],
            "property_address": r[2],
            "permit_number": r[3],
            "pdf_hash": r[4],
            "structural_fingerprint": _load_fp(r[5]),
        }
        for r in rows
    ]


def _load_fp(raw) -> list[dict]:
    """Parse structural_fingerprint from DB (stored as JSON text or JSONB)."""
    if raw is None:
        return []
    if isinstance(raw, list):
        return raw  # already parsed (psycopg2 JSONB auto-decode)
    try:
        return json.loads(raw)
    except Exception:
        return []


# ── Phase 2: post-analysis linking ───────────────────────────────


def find_matching_job(
    *,
    user_id: int,
    current_job_id: str,
    current_fp: list[dict],
    current_hash: str | None,
    filename: str,
    property_address: str | None,
    permit_number: str | None,
) -> str | None:
    """Find the best-matching previous job for version group assignment.

    Called after vision processing completes with structural fingerprint.
    Returns the job_id of the best match, or None if no match above threshold.

    Match priority:
      1. Exact content hash (Layer 1) — highest confidence
      2. Structural overlap >= 60% (Layer 2)
      3. Metadata-only match (Layer 3) — only if no structural data available
    """
    candidates = find_candidate_jobs(
        user_id=user_id,
        exclude_job_id=current_job_id,
        pdf_hash=current_hash,
        filename=filename,
        property_address=property_address,
        permit_number=permit_number,
    )

    if not candidates:
        return None

    best_job_id = None
    best_score = 0.0

    for cand in candidates:
        # Layer 1: exact hash match — instant win
        if current_hash and cand["pdf_hash"] and current_hash == cand["pdf_hash"]:
            return cand["job_id"]

        # Layer 2: structural overlap
        cand_fp = cand["structural_fingerprint"]
        if current_fp and cand_fp:
            score = compute_overlap_score(current_fp, cand_fp)
            if score > best_score:
                best_score = score
                best_job_id = cand["job_id"]
            continue

        # Layer 3: metadata only (no structural data on either side)
        if not current_fp and not cand_fp:
            # Treat any metadata match as a weak link (score 0.5)
            if metadata_matches(
                {"filename": filename, "property_address": property_address, "permit_number": permit_number},
                cand,
            ):
                if 0.5 > best_score:
                    best_score = 0.5
                    best_job_id = cand["job_id"]

    if best_score >= OVERLAP_THRESHOLD:
        return best_job_id
    return None
