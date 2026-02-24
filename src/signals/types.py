"""Signal type definitions and catalog for severity v2."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SignalType:
    signal_type: str
    default_severity: str
    source_dataset: str
    actionable: str
    description: str


@dataclass
class Signal:
    signal_type: str
    severity: str
    permit_number: str | None
    block_lot: str
    detail: str


@dataclass
class PropertyHealth:
    block_lot: str
    tier: str
    signal_count: int
    at_risk_count: int
    signals: list[Signal] = field(default_factory=list)


SIGNAL_CATALOG: dict[str, SignalType] = {
    "hold_comments": SignalType(
        "hold_comments", "at_risk", "addenda", "yes",
        "Reviewer issued corrections via Issued Comments",
    ),
    "hold_stalled_planning": SignalType(
        "hold_stalled_planning", "at_risk", "addenda", "yes",
        "Stalled 1yr+ at PPC/CP-ZOC/CPB planning station",
    ),
    "hold_stalled": SignalType(
        "hold_stalled", "behind", "addenda", "warning",
        "Stalled 30d+ at non-planning station",
    ),
    "nov": SignalType(
        "nov", "at_risk", "violations", "yes",
        "Open Notice of Violation",
    ),
    "abatement": SignalType(
        "abatement", "at_risk", "violations", "yes",
        "Order of Abatement or Directors Hearing",
    ),
    "expired_uninspected": SignalType(
        "expired_uninspected", "at_risk", "permits+inspections", "yes",
        "Expired with 4+ real inspections, no final",
    ),
    "stale_with_activity": SignalType(
        "stale_with_activity", "at_risk", "permits+inspections", "yes",
        "Issued 2yr+, latest real inspection within 5yr, 2+ real inspections",
    ),
    "expired_minor_activity": SignalType(
        "expired_minor_activity", "behind", "permits+inspections", "warning",
        "Expired with 1-3 real inspections",
    ),
    "expired_inconclusive": SignalType(
        "expired_inconclusive", "behind", "permits", "warning",
        "Expired, zero real inspections, non-OTC",
    ),
    "complaint": SignalType(
        "complaint", "slower", "complaints", "info",
        "Open complaint, no associated NOV",
    ),
    "expired_otc": SignalType(
        "expired_otc", "slower", "permits", "info",
        "Expired, zero real inspections, OTC type",
    ),
    "stale_no_activity": SignalType(
        "stale_no_activity", "slower", "permits", "info",
        "Issued 2yr+, no meaningful recent inspections",
    ),
    "station_slow": SignalType(
        "station_slow", "behind", "addenda+velocity", "warning",
        "Station dwell exceeding velocity baseline",
    ),
}
