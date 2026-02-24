"""Severity v2 — signal-based property health model."""

from src.signals.types import Signal, SignalType, PropertyHealth, SIGNAL_CATALOG
from src.signals.aggregator import compute_property_health, COMPOUNDING_TYPES
from src.signals.pipeline import run_signal_pipeline

__all__ = [
    "Signal",
    "SignalType",
    "PropertyHealth",
    "SIGNAL_CATALOG",
    "compute_property_health",
    "COMPOUNDING_TYPES",
    "run_signal_pipeline",
]
