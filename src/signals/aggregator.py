"""Property-level health aggregation — tier derivation + HIGH_RISK logic.

Implements the validated compound signal model (Session 50):
- HIGH_RISK fires when 2+ independent AT_RISK signals from different COMPOUNDING types
- Only specific signal types compound (hold_comments, hold_stalled_planning, nov,
  abatement, expired_uninspected, stale_with_activity)
- hold_stalled (behind) does NOT compound
- complaint (slower) does NOT compound

Sprint 66: Added recency-weighted scoring for signal prioritization.
"""

from __future__ import annotations

from datetime import date, timedelta

from src.signals.types import Signal, PropertyHealth, COMPOUNDING_TYPES


# Recency half-life: signals older than this many days receive reduced weight
RECENCY_HALF_LIFE_DAYS = 90


def _recency_weight(detected_at: date | str | None) -> float:
    """Compute a recency weight for a signal based on its detection date.

    Returns a float between 0.1 and 1.0:
    - Today: 1.0
    - RECENCY_HALF_LIFE_DAYS ago: 0.5
    - 2x half-life: 0.25
    - Minimum: 0.1 (signals never fully expire)

    If detected_at is None, returns 1.0 (assume recent).
    """
    if detected_at is None:
        return 1.0

    if isinstance(detected_at, str):
        try:
            detected_at = date.fromisoformat(detected_at[:10])
        except (ValueError, TypeError):
            return 1.0

    days_ago = (date.today() - detected_at).days
    if days_ago <= 0:
        return 1.0

    # Exponential decay with half-life
    weight = 0.5 ** (days_ago / RECENCY_HALF_LIFE_DAYS)
    return max(weight, 0.1)


def compute_property_health(block_lot: str, signals: list[Signal]) -> PropertyHealth:
    """Derive the health tier for a property from its signals.

    Tier derivation (from spec):
        1. Count AT_RISK signals from COMPOUNDING_TYPES
        2. If 2+ unique compounding types → high_risk
        3. Elif any at_risk → at_risk
        4. Elif any behind → behind
        5. Elif any slower → slower
        6. Else → on_track
    """
    at_risk = [s for s in signals if s.severity == "at_risk"]
    compounding = [s for s in at_risk if s.signal_type in COMPOUNDING_TYPES]
    unique_compounding_types = set(s.signal_type for s in compounding)

    if len(unique_compounding_types) >= 2:
        tier = "high_risk"
    elif len(at_risk) >= 1:
        tier = "at_risk"
    elif any(s.severity == "behind" for s in signals):
        tier = "behind"
    elif any(s.severity == "slower" for s in signals):
        tier = "slower"
    else:
        tier = "on_track"

    return PropertyHealth(
        block_lot=block_lot,
        tier=tier,
        signal_count=len(signals),
        at_risk_count=len(at_risk),
        signals=signals,
    )


def sort_signals_by_recency(signals: list[Signal]) -> list[Signal]:
    """Sort signals by recency weight (most recent first).

    Uses the `detected_at` attribute if present on the signal,
    otherwise treats as maximally recent. This allows callers to
    prioritize fresh signals when displaying or acting on property health.
    """
    def _sort_key(s: Signal) -> float:
        detected = getattr(s, "detected_at", None)
        return -_recency_weight(detected)
    return sorted(signals, key=_sort_key)
