"""Property-level health tier derivation from signals.

HIGH_RISK fires when 2+ independent AT_RISK-level signals from different
COMPOUNDING signal types converge on one property.
"""

from __future__ import annotations

from src.signals.types import Signal, PropertyHealth

COMPOUNDING_TYPES = frozenset({
    "hold_comments",
    "hold_stalled_planning",
    "nov",
    "abatement",
    "expired_uninspected",
    "stale_with_activity",
})


def compute_property_health(block_lot: str, signals: list[Signal]) -> PropertyHealth:
    """Derive property-level health tier from a list of signals.

    Tier derivation:
      1. high_risk  — 2+ distinct COMPOUNDING types at at_risk severity
      2. at_risk    — 1+ at_risk signal
      3. behind     — any 'behind' signal
      4. slower     — any 'slower' signal
      5. on_track   — no signals
    """
    at_risk_signals = [s for s in signals if s.severity == "at_risk"]
    compounding = [s for s in at_risk_signals if s.signal_type in COMPOUNDING_TYPES]
    unique_compounding_types = set(s.signal_type for s in compounding)

    if len(unique_compounding_types) >= 2:
        tier = "high_risk"
    elif len(at_risk_signals) >= 1:
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
        at_risk_count=len(at_risk_signals),
        signals=signals,
    )
