"""Signal type definitions and catalog for severity v2.

The signal catalog is the source of truth for all signal types, their default
severities, source datasets, and actionability. Changes to signal behavior
should happen here (config), not in detector code.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SignalType:
    """Definition of a signal type in the catalog."""
    signal_type: str
    default_severity: str  # at_risk, behind, slower
    source_dataset: str
    actionable: str  # yes, warning, info
    description: str


@dataclass
class Signal:
    """A detected signal instance."""
    signal_type: str
    severity: str
    permit_number: str | None
    block_lot: str
    detail: str


@dataclass
class PropertyHealth:
    """Aggregated health tier for a property (block_lot)."""
    block_lot: str
    tier: str  # high_risk, at_risk, behind, slower, on_track
    signal_count: int
    at_risk_count: int
    signals: list[Signal] = field(default_factory=list)


# Signal types that compound into HIGH_RISK when 2+ are present on a property.
# Only AT_RISK-level signals from independent sources compound.
# hold_stalled (behind) does NOT compound.
# complaint (slower) does NOT compound.
COMPOUNDING_TYPES = {
    "hold_comments",
    "hold_stalled_planning",
    "nov",
    "abatement",
    "expired_uninspected",
    "stale_with_activity",
}

# Complete signal catalog — 13 types
SIGNAL_CATALOG: dict[str, SignalType] = {
    "hold_comments": SignalType(
        signal_type="hold_comments",
        default_severity="at_risk",
        source_dataset="addenda",
        actionable="yes",
        description="Reviewer issued corrections via Issued Comments",
    ),
    "hold_stalled_planning": SignalType(
        signal_type="hold_stalled_planning",
        default_severity="at_risk",
        source_dataset="addenda",
        actionable="yes",
        description="Stalled 1yr+ at PPC/CP-ZOC/CPB planning station",
    ),
    "hold_stalled": SignalType(
        signal_type="hold_stalled",
        default_severity="behind",
        source_dataset="addenda",
        actionable="warning",
        description="Stalled 30d+ at non-planning station",
    ),
    "nov": SignalType(
        signal_type="nov",
        default_severity="at_risk",
        source_dataset="violations",
        actionable="yes",
        description="Open Notice of Violation",
    ),
    "abatement": SignalType(
        signal_type="abatement",
        default_severity="at_risk",
        source_dataset="violations",
        actionable="yes",
        description="Order of Abatement or Directors Hearing",
    ),
    "expired_uninspected": SignalType(
        signal_type="expired_uninspected",
        default_severity="at_risk",
        source_dataset="permits+inspections",
        actionable="yes",
        description="Expired with 4+ real inspections, no final",
    ),
    "stale_with_activity": SignalType(
        signal_type="stale_with_activity",
        default_severity="at_risk",
        source_dataset="permits+inspections",
        actionable="yes",
        description="Issued 2yr+, latest real inspection within 5yr, 2+ real inspections",
    ),
    "expired_minor_activity": SignalType(
        signal_type="expired_minor_activity",
        default_severity="behind",
        source_dataset="permits+inspections",
        actionable="warning",
        description="Expired with 1-3 real inspections",
    ),
    "expired_inconclusive": SignalType(
        signal_type="expired_inconclusive",
        default_severity="behind",
        source_dataset="permits",
        actionable="warning",
        description="Expired, zero real inspections, non-OTC type",
    ),
    "complaint": SignalType(
        signal_type="complaint",
        default_severity="slower",
        source_dataset="complaints",
        actionable="info",
        description="Open complaint, no associated NOV",
    ),
    "expired_otc": SignalType(
        signal_type="expired_otc",
        default_severity="slower",
        source_dataset="permits",
        actionable="info",
        description="Expired, zero real inspections, OTC type",
    ),
    "stale_no_activity": SignalType(
        signal_type="stale_no_activity",
        default_severity="slower",
        source_dataset="permits",
        actionable="info",
        description="Issued 2yr+, no meaningful recent inspections",
    ),
    "station_slow": SignalType(
        signal_type="station_slow",
        default_severity="behind",
        source_dataset="addenda+velocity",
        actionable="warning",
        description="Station dwell exceeding velocity baseline",
    ),
}
