"""Property-level health aggregation — tier derivation + HIGH_RISK logic.

Implements the validated compound signal model (Session 50):
- HIGH_RISK fires when 2+ independent AT_RISK signals from different COMPOUNDING types
- Only specific signal types compound (hold_comments, hold_stalled_planning, nov,
  abatement, expired_uninspected, stale_with_activity)
- hold_stalled (behind) does NOT compound
- complaint (slower) does NOT compound
"""

from __future__ import annotations

from src.signals.types import Signal, PropertyHealth, COMPOUNDING_TYPES


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
