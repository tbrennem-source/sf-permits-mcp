"""Phase E2: Plan analysis comparison engine.

Computes a structured diff between two completed plan analysis jobs (v1 and v2)
and caches the result as `comparison_json` on the newer job.

Algorithm per SPEC-analysis-history-phases-d-f.md (AMB-1 resolution):

Comment matching:
  1. Bucket v1 and v2 annotations by `type`
  2. For each v2 annotation, find v1 candidates of same type
  3. Token overlap (uppercase, split on whitespace/punctuation)
  4. Threshold: 2 shared tokens (1 for type="stamp")
  5. Tiebreak: smallest Euclidean distance (x, y)
  6. Classify: resolved / unchanged / new

Sheet diff:
  - Compare (page_number, sheet_number) sets from structural_fingerprint
  - Added: in v2, not in v1; Removed: in v1, not in v2; Unchanged: in both

EPR changes:
  - Compare metadata_results check_id → v1_status / v2_status (if changed)

Cache invalidation:
  - comparison_json stored on v2 job
  - Re-compute when v2's completed_at > comparison_json["computed_at"]
"""

import json
import logging
import math
import re
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Token overlap helpers
# ---------------------------------------------------------------------------

_TOKEN_SPLIT = re.compile(r"[^A-Z0-9]+")


def _tokenize(text: str) -> set[str]:
    """Uppercase, split on whitespace/punctuation, drop empty tokens."""
    return {t for t in _TOKEN_SPLIT.split(text.upper()) if t}


def _token_overlap(a: str, b: str) -> int:
    """Count shared tokens between two strings."""
    return len(_tokenize(a) & _tokenize(b))


def _euclid(ann_a: dict, ann_b: dict) -> float:
    """Euclidean distance in (x, y) percentage-space."""
    dx = ann_a.get("x", 0) - ann_b.get("x", 0)
    dy = ann_a.get("y", 0) - ann_b.get("y", 0)
    return math.sqrt(dx * dx + dy * dy)


# ---------------------------------------------------------------------------
# Comment matching (AMB-1 algorithm)
# ---------------------------------------------------------------------------

def match_comments(
    v1_annotations: list[dict],
    v2_annotations: list[dict],
) -> list[dict]:
    """Match v2 annotations to v1 annotations using token overlap + position tiebreak.

    Returns a list of resolution dicts:
      {
        "v1_label":   str | None,
        "v1_type":    str | None,
        "v2_label":   str | None,
        "v2_type":    str | None,
        "status":     "resolved" | "unchanged" | "new",
        "v1_importance": str | None,
        "v2_importance": str | None,
        "page_number": int | None,  # from v2 (or v1 for resolved)
      }
    """
    # Bucket v1 by type for fast lookup
    v1_by_type: dict[str, list[dict]] = {}
    for ann in v1_annotations:
        t = ann.get("type", "")
        v1_by_type.setdefault(t, []).append(ann)

    # Track which v1 annotations have been matched (by index in original list)
    v1_matched: set[int] = set()
    # Build a stable index across the full v1 list
    v1_index = {id(a): i for i, a in enumerate(v1_annotations)}

    resolutions: list[dict] = []

    for v2_ann in v2_annotations:
        v2_type = v2_ann.get("type", "")
        v2_label = v2_ann.get("label", "")
        # Threshold: 1 for stamp, 2 for everything else (AMB-1 resolution)
        threshold = 1 if v2_type == "stamp" else 2

        candidates = v1_by_type.get(v2_type, [])

        best_v1 = None
        best_overlap = 0
        best_dist = float("inf")

        for v1_ann in candidates:
            v1_idx = v1_index[id(v1_ann)]
            if v1_idx in v1_matched:
                continue  # already consumed
            overlap = _token_overlap(v2_label, v1_ann.get("label", ""))
            if overlap < threshold:
                continue
            # Prefer higher overlap; break ties by position proximity
            dist = _euclid(v2_ann, v1_ann)
            if overlap > best_overlap or (overlap == best_overlap and dist < best_dist):
                best_overlap = overlap
                best_dist = dist
                best_v1 = v1_ann

        if best_v1 is not None:
            v1_idx = v1_index[id(best_v1)]
            v1_matched.add(v1_idx)

            # Determine status: resolved if importance dropped or v2 has lower severity
            v1_imp = best_v1.get("importance", "medium")
            v2_imp = v2_ann.get("importance", "medium")
            imp_order = {"high": 2, "medium": 1, "low": 0}
            if imp_order.get(v2_imp, 1) < imp_order.get(v1_imp, 1):
                status = "resolved"
            else:
                status = "unchanged"

            resolutions.append({
                "v1_label": best_v1.get("label"),
                "v1_type": v2_type,
                "v2_label": v2_label,
                "v2_type": v2_type,
                "status": status,
                "v1_importance": v1_imp,
                "v2_importance": v2_imp,
                "page_number": v2_ann.get("page_number") or best_v1.get("page_number"),
            })
        else:
            # No v1 match → new comment in v2
            resolutions.append({
                "v1_label": None,
                "v1_type": None,
                "v2_label": v2_label,
                "v2_type": v2_type,
                "status": "new",
                "v1_importance": None,
                "v2_importance": v2_ann.get("importance", "medium"),
                "page_number": v2_ann.get("page_number"),
            })

    # Any unmatched v1 annotations → resolved (present in v1 but absent in v2)
    for v1_ann in v1_annotations:
        v1_idx = v1_index[id(v1_ann)]
        if v1_idx not in v1_matched:
            resolutions.append({
                "v1_label": v1_ann.get("label"),
                "v1_type": v1_ann.get("type"),
                "v2_label": None,
                "v2_type": None,
                "status": "resolved",
                "v1_importance": v1_ann.get("importance", "medium"),
                "v2_importance": None,
                "page_number": v1_ann.get("page_number"),
            })

    return resolutions


# ---------------------------------------------------------------------------
# Sheet diff
# ---------------------------------------------------------------------------

def compute_sheet_diff(
    v1_fingerprint: list[dict],
    v2_fingerprint: list[dict],
) -> dict:
    """Diff (page_number, sheet_number) sets between two fingerprints.

    Returns:
      {
        "added":     [str, ...],   # sheet_numbers in v2 not in v1
        "removed":   [str, ...],   # sheet_numbers in v1 not in v2
        "unchanged": [str, ...],   # sheet_numbers in both
      }
    where sheets with sheet_number=None are represented as "p{page_number}".
    """
    def _sheet_label(p: dict) -> str:
        return p["sheet_number"] if p.get("sheet_number") else f"p{p['page_number']}"

    v1_sheets = {_sheet_label(p) for p in v1_fingerprint}
    v2_sheets = {_sheet_label(p) for p in v2_fingerprint}

    return {
        "added": sorted(v2_sheets - v1_sheets),
        "removed": sorted(v1_sheets - v2_sheets),
        "unchanged": sorted(v1_sheets & v2_sheets),
    }


# ---------------------------------------------------------------------------
# EPR check diff
# ---------------------------------------------------------------------------

def compute_epr_diff(
    v1_extractions: list[dict],
    v2_extractions: list[dict],
) -> list[dict]:
    """Diff EPR check results between two sets of page extractions.

    Each extraction may contain 'epr_checks': [{check_id, status, ...}].
    Returns list of changes where status differs:
      [{"check_id": "EPR-012", "v1_status": "FAIL", "v2_status": "PASS"}, ...]
    """
    def _collect_checks(extractions: list[dict]) -> dict[str, str]:
        """Return {check_id: worst_status} across all pages."""
        STATUS_ORDER = {"FAIL": 3, "WARN": 2, "PASS": 1, "SKIP": 0, "INFO": 0}
        result: dict[str, str] = {}
        for ext in extractions:
            for chk in ext.get("epr_checks", []) or []:
                cid = chk.get("check_id") or chk.get("id")
                status = chk.get("status", "")
                if not cid:
                    continue
                if cid not in result or STATUS_ORDER.get(status, 0) > STATUS_ORDER.get(result[cid], 0):
                    result[cid] = status
        return result

    v1_checks = _collect_checks(v1_extractions)
    v2_checks = _collect_checks(v2_extractions)

    all_ids = sorted(set(v1_checks) | set(v2_checks))
    changes = []
    for cid in all_ids:
        v1_s = v1_checks.get(cid, "N/A")
        v2_s = v2_checks.get(cid, "N/A")
        if v1_s != v2_s:
            changes.append({"check_id": cid, "v1_status": v1_s, "v2_status": v2_s})
    return changes


# ---------------------------------------------------------------------------
# Summary counts
# ---------------------------------------------------------------------------

def _build_summary(
    resolutions: list[dict],
    sheet_diff: dict,
) -> dict:
    resolved = sum(1 for r in resolutions if r["status"] == "resolved")
    new = sum(1 for r in resolutions if r["status"] == "new")
    unchanged = sum(1 for r in resolutions if r["status"] == "unchanged")
    return {
        "resolved": resolved,
        "new": new,
        "unchanged": unchanged,
        "sheets_added": len(sheet_diff.get("added", [])),
        "sheets_removed": len(sheet_diff.get("removed", [])),
    }


# ---------------------------------------------------------------------------
# Top-level computation
# ---------------------------------------------------------------------------

def compute_comparison(
    job_a: dict,
    session_a: dict,
    job_b: dict,
    session_b: dict,
) -> dict:
    """Compute full comparison between job_a (v1) and job_b (v2).

    job_a / job_b: dicts from get_job() (must include structural_fingerprint)
    session_a / session_b: dicts from get_session() with page_extractions
      and page_annotations

    Returns the comparison_json dict (not yet serialized):
      {
        "computed_at": ISO string,
        "job_a_id": str,
        "job_b_id": str,
        "comment_resolutions": [...],
        "epr_changes": [...],
        "sheet_diff": {...},
        "summary": {...},
      }
    """
    # Load structural fingerprints from job row (already stored as JSON text)
    def _load_fp(job: dict) -> list[dict]:
        raw = job.get("structural_fingerprint")
        if raw is None:
            return []
        if isinstance(raw, list):
            return raw
        try:
            return json.loads(raw)
        except Exception:
            return []

    v1_fp = _load_fp(job_a)
    v2_fp = _load_fp(job_b)

    v1_annotations = session_a.get("page_annotations") or []
    v2_annotations = session_b.get("page_annotations") or []
    v1_extractions = session_a.get("page_extractions") or []
    v2_extractions = session_b.get("page_extractions") or []

    resolutions = match_comments(v1_annotations, v2_annotations)
    sheet_diff = compute_sheet_diff(v1_fp, v2_fp)
    epr_changes = compute_epr_diff(v1_extractions, v2_extractions)
    summary = _build_summary(resolutions, sheet_diff)

    return {
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "job_a_id": job_a["job_id"],
        "job_b_id": job_b["job_id"],
        "comment_resolutions": resolutions,
        "epr_changes": epr_changes,
        "sheet_diff": sheet_diff,
        "summary": summary,
    }


# ---------------------------------------------------------------------------
# DB cache helpers
# ---------------------------------------------------------------------------

def get_cached_comparison(job_b_id: str) -> dict | None:
    """Return cached comparison_json for job_b, or None if stale/absent.

    Cache is stale if job_b's completed_at is newer than comparison_json.computed_at.
    """
    from src.db import query_one

    row = query_one(
        "SELECT comparison_json, completed_at FROM plan_analysis_jobs WHERE job_id = %s",
        (job_b_id,),
    )
    if not row or not row[0]:
        return None

    raw = row[0]
    completed_at = row[1]

    try:
        cached = json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        return None

    # Validate cache is fresh vs completed_at
    computed_at_str = cached.get("computed_at")
    if computed_at_str and completed_at:
        try:
            computed_at = datetime.fromisoformat(computed_at_str)
            # Make completed_at timezone-aware if it isn't
            if completed_at.tzinfo is None:
                completed_at = completed_at.replace(tzinfo=timezone.utc)
            if computed_at.tzinfo is None:
                computed_at = computed_at.replace(tzinfo=timezone.utc)
            if completed_at > computed_at:
                return None  # Stale — job was reprocessed after cache was built
        except Exception:
            pass  # Can't determine staleness — serve cached version

    return cached


def store_comparison(job_b_id: str, comparison: dict) -> None:
    """Persist comparison_json to the job_b row."""
    from src.db import execute_write

    execute_write(
        "UPDATE plan_analysis_jobs SET comparison_json = %s WHERE job_id = %s",
        (json.dumps(comparison), job_b_id),
    )


def get_or_compute_comparison(
    job_a: dict,
    session_a: dict,
    job_b: dict,
    session_b: dict,
) -> dict:
    """Return cached comparison or compute + store a fresh one.

    job_b is always the newer version; comparison_json is stored on job_b.
    """
    cached = get_cached_comparison(job_b["job_id"])
    if cached is not None:
        return cached

    comparison = compute_comparison(job_a, session_a, job_b, session_b)
    try:
        store_comparison(job_b["job_id"], comparison)
    except Exception:
        logger.warning("Failed to cache comparison for job %s", job_b["job_id"], exc_info=True)

    return comparison
