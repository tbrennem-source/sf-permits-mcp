"""Permit Severity Scoring Model — data-driven 0-100 severity score.

Pure functions, no database dependency. Scores permits across 5 dimensions:
  1. Inspection Activity (25%) — has inspections vs. expected for category
  2. Age/Staleness (25%) — days filed + days since last activity
  3. Expiration Proximity (20%) — Table B countdown
  4. Cost Tier (15%) — higher cost = higher impact if abandoned
  5. Category Risk (15%) — life-safety categories score higher

Tier thresholds: CRITICAL >=80, HIGH >=60, MEDIUM >=40, LOW >=20, GREEN <20.

Based on analysis of 1.1M+ permits and 671K inspections:
  - 92.6% of stale issued permits (filed >2yr) have zero inspections
  - Life-safety categories (seismic 37.3%, ADU 37.8%) most reliably inspected
  - Fire Safety (6.2%) and Solar (10.9%) have lowest inspection rates
  - 91.1% of completed alterations have zero inspection records
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class PermitInput:
    """Minimal permit data needed for severity scoring."""

    permit_number: str
    status: str = ""
    permit_type_definition: str = ""
    description: str = ""
    filed_date: date | None = None
    issued_date: date | None = None
    completed_date: date | None = None
    status_date: date | None = None
    estimated_cost: float = 0.0
    revised_cost: float | None = None
    inspection_count: int = 0

    @classmethod
    def from_dict(cls, d: dict, inspection_count: int = 0) -> PermitInput:
        """Build from a permit dict (e.g. from DB row or API response)."""
        return cls(
            permit_number=d.get("permit_number", ""),
            status=(d.get("status") or "").lower(),
            permit_type_definition=d.get("permit_type_definition") or "",
            description=d.get("description") or "",
            filed_date=_parse_date(d.get("filed_date")),
            issued_date=_parse_date(d.get("issued_date")),
            completed_date=_parse_date(d.get("completed_date")),
            status_date=_parse_date(d.get("status_date")),
            estimated_cost=_parse_cost(d.get("estimated_cost")),
            revised_cost=_parse_cost(d.get("revised_cost")),
            inspection_count=inspection_count,
        )


@dataclass
class SeverityResult:
    """Output of the severity scoring model."""

    score: int  # 0-100
    tier: str  # CRITICAL, HIGH, MEDIUM, LOW, GREEN
    dimensions: dict[str, dict] = field(default_factory=dict)
    top_driver: str = ""
    explanation: str = ""
    confidence: str = "high"  # high, medium, low
    category: str = "general"


# ---------------------------------------------------------------------------
# Constants — data-driven from permit/inspection analysis
# ---------------------------------------------------------------------------

# Keyword-to-category mapping (12 categories).
# Order matters: first match wins for ambiguous descriptions.
DESCRIPTION_CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "seismic_structural": [
        "seismic", "earthquake", "retrofit", "soft story", "foundation bolting",
        "brace and bolt", "cripple wall", "ebb", "house bolting",
    ],
    "fire_safety": [
        "fire alarm", "fire sprinkler", "fire suppression", "fire escape",
        "fire rated", "smoke detector", "fire protection",
    ],
    "adu": [
        "adu", "accessory dwelling", "in-law", "granny flat",
        "garage conversion to dwelling", "secondary unit",
    ],
    "new_construction": [
        "new construction", "new building", "ground up", "erect",
        "new structure", "construct new",
    ],
    "kitchen_bath": [
        "kitchen remodel", "bathroom remodel", "kitchen renovation",
        "bath renovation", "new kitchen", "new bathroom",
    ],
    "electrical": [
        "electrical", "wiring", "panel upgrade", "service upgrade",
        "outlet", "circuit",
    ],
    "plumbing": [
        "plumbing", "water heater", "sewer", "drain", "gas line",
        "water line", "repipe",
    ],
    "structural": [
        "structural", "load bearing", "shear wall", "foundation",
        "beam", "column", "retaining wall",
    ],
    "windows_doors": [
        "window", "door", "skylight", "glazing",
    ],
    "reroofing": [
        "reroof", "re-roof", "roofing", "new roof", "roof replacement",
    ],
    "solar": [
        "solar", "photovoltaic", "pv panel", "battery storage",
        "ev charger", "ev charging",
    ],
    "demolition": [
        "demolition", "demolish", "tear down", "raze",
    ],
}

# Average inspections per category when inspections ARE present.
# From analysis: categories where inspections happen, how many on average.
EXPECTED_INSPECTIONS: dict[str, float] = {
    "seismic_structural": 4.2,
    "fire_safety": 3.5,
    "adu": 6.8,
    "new_construction": 8.5,
    "kitchen_bath": 3.0,
    "electrical": 2.5,
    "plumbing": 2.5,
    "structural": 4.0,
    "windows_doors": 1.5,
    "reroofing": 1.2,
    "solar": 1.5,
    "demolition": 2.0,
    "general": 2.0,
}

# Categories grouped by inspection reliability
LIFE_SAFETY_CATEGORIES = {"seismic_structural", "fire_safety", "structural"}
HIGH_INSPECTION_CATEGORIES = {"kitchen_bath", "adu", "new_construction"}
MODERATE_CATEGORIES = {"electrical", "plumbing", "windows_doors"}

# Intrinsic category risk scores (0-100).
# Life-safety = highest, cosmetic = lowest.
CATEGORY_RISK_SCORES: dict[str, int] = {
    "seismic_structural": 100,
    "structural": 90,
    "fire_safety": 85,
    "new_construction": 80,
    "adu": 70,
    "demolition": 65,
    "electrical": 55,
    "plumbing": 50,
    "kitchen_bath": 45,
    "windows_doors": 25,
    "solar": 20,
    "reroofing": 10,
    "general": 30,
}

# Table B (SFBC 106A.4.4) — permit validity by valuation.
_TABLE_B_TIERS = [
    (2_500_000, 1440),
    (100_001, 1080),
    (0, 360),
]
_DEMOLITION_VALIDITY = 180

# Dimension weights (must sum to 1.0)
_W_INSPECTION = 0.25
_W_AGE = 0.25
_W_EXPIRATION = 0.20
_W_COST = 0.15
_W_CATEGORY = 0.15

# Tier thresholds
_TIER_THRESHOLDS = [
    (80, "CRITICAL"),
    (60, "HIGH"),
    (40, "MEDIUM"),
    (20, "LOW"),
    (0, "GREEN"),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_date(val) -> date | None:
    """Parse a date from string, date, or None."""
    if val is None:
        return None
    if isinstance(val, date):
        return val
    try:
        text = str(val).strip()[:10]
        return date.fromisoformat(text)
    except (ValueError, TypeError):
        return None


def _parse_cost(val) -> float | None:
    """Parse a cost value."""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _validity_days(permit_type_def: str, cost: float) -> int:
    """Table B expiration period based on permit type and valuation."""
    if "demolition" in permit_type_def.lower():
        return _DEMOLITION_VALIDITY
    for threshold, days in _TABLE_B_TIERS:
        if cost >= threshold:
            return days
    return 360


def _score_to_tier(score: int) -> str:
    """Map a 0-100 score to a tier name."""
    for threshold, tier in _TIER_THRESHOLDS:
        if score >= threshold:
            return tier
    return "GREEN"


def _clamp(val: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, val))


# ---------------------------------------------------------------------------
# Description classification
# ---------------------------------------------------------------------------

def classify_description(description: str, permit_type_def: str = "") -> str:
    """Classify a permit description into one of 12 categories + 'general' fallback.

    Checks both the description and the permit_type_definition field.
    First match wins (categories are ordered by specificity).
    """
    text = f"{description} {permit_type_def}".lower()

    for category, keywords in DESCRIPTION_CATEGORY_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return category

    return "general"


# ---------------------------------------------------------------------------
# Dimension scorers (each returns 0-100, higher = more severe)
# ---------------------------------------------------------------------------

def _score_inspection_activity(permit: PermitInput, category: str, today: date) -> float:
    """Score based on inspection activity relative to expectations.

    Higher score = more concerning (fewer inspections than expected).
    """
    status = permit.status.lower()

    # Filed/approved permits don't need inspections yet — no penalty
    if status in ("filed", "approved", ""):
        return 0.0

    # Completed permits with zero inspections — suspicious for high-risk categories
    expected = EXPECTED_INSPECTIONS.get(category, 2.0)
    actual = permit.inspection_count

    if status == "complete":
        if actual == 0:
            # Life-safety with 0 inspections is very concerning
            if category in LIFE_SAFETY_CATEGORIES:
                return 90.0
            if category in HIGH_INSPECTION_CATEGORIES:
                return 70.0
            # General/moderate — zero inspections is common (91.1% of alterations)
            return 30.0
        # Has some inspections — compare to expected
        ratio = actual / expected
        if ratio >= 1.0:
            return 0.0
        return _clamp((1.0 - ratio) * 50.0)

    # Issued permits — inspections expected if construction should be underway
    if status == "issued":
        if permit.issued_date:
            days_issued = (today - permit.issued_date).days
            if days_issued < 30:
                # Just issued — too early for inspections
                return 0.0
            if actual == 0:
                # No inspections and issued for a while
                staleness = min(days_issued / 365.0, 2.0)  # cap at 2 years
                if category in LIFE_SAFETY_CATEGORIES:
                    return _clamp(40.0 + staleness * 30.0)
                return _clamp(20.0 + staleness * 20.0)
            # Has inspections — compare to expected
            ratio = actual / expected
            if ratio >= 0.5:
                return 0.0
            return _clamp((0.5 - ratio) * 40.0)

    return 0.0


def _score_age_staleness(permit: PermitInput, today: date) -> float:
    """Score based on permit age and time since last activity.

    Higher score = older/more stale.
    """
    score = 0.0

    # Age component: days since filing
    if permit.filed_date:
        days_filed = (today - permit.filed_date).days
        if days_filed > 0:
            # Ramp: 0d=0, 365d=30, 730d=60, 1095d=80, 1460d+=100
            score = _clamp(days_filed / 1460.0 * 100.0)

    # Staleness component: days since last activity
    if permit.status_date:
        days_since = (today - permit.status_date).days
        if days_since > 60:
            # Stalled — boost score
            stale_boost = _clamp((days_since - 60) / 300.0 * 40.0, 0.0, 40.0)
            score = _clamp(score + stale_boost)

    # Completed permits get a big reduction — they're done
    if permit.status.lower() == "complete":
        score *= 0.1

    return _clamp(score)


def _score_expiration_proximity(permit: PermitInput, today: date) -> float:
    """Score based on proximity to Table B expiration deadline.

    Only applies to issued permits (not filed, approved, or complete).
    Higher score = closer to or past expiration.
    """
    if permit.status.lower() != "issued" or not permit.issued_date:
        return 0.0

    cost = permit.revised_cost if permit.revised_cost is not None else (permit.estimated_cost or 0.0)
    validity = _validity_days(permit.permit_type_definition, cost)
    days_issued = (today - permit.issued_date).days
    expires_in = validity - days_issued

    if expires_in <= 0:
        return 100.0  # Already expired
    if expires_in <= 30:
        return 90.0
    if expires_in <= 90:
        return 70.0
    if expires_in <= 180:
        return 50.0
    if expires_in <= 360:
        # Linear ramp: 360d → 0, 180d → 25
        return _clamp((360.0 - expires_in) / 180.0 * 25.0, 0.0, 25.0)

    return 0.0


def _score_cost_tier(permit: PermitInput) -> float:
    """Score based on project cost — higher cost = higher impact if abandoned.

    Scale: $0=0, $50k=20, $200k=40, $500k=60, $1M=80, $2.5M+=100.
    """
    cost = permit.revised_cost if permit.revised_cost is not None else (permit.estimated_cost or 0.0)
    if cost <= 0:
        return 0.0
    if cost >= 2_500_000:
        return 100.0
    if cost >= 1_000_000:
        return 80.0
    if cost >= 500_000:
        return 60.0
    if cost >= 200_000:
        return 40.0
    if cost >= 50_000:
        return 20.0
    return 10.0


def _score_category_risk(category: str) -> float:
    """Score based on intrinsic category risk."""
    return float(CATEGORY_RISK_SCORES.get(category, 30))


# ---------------------------------------------------------------------------
# Main scoring function
# ---------------------------------------------------------------------------

def score_permit(permit: PermitInput, today: date | None = None) -> SeverityResult:
    """Score a single permit on 0-100 severity scale.

    Args:
        permit: PermitInput with permit data.
        today: Override for current date (for testing).

    Returns:
        SeverityResult with score, tier, dimension breakdown, and explanation.
    """
    if today is None:
        today = date.today()

    category = classify_description(permit.description, permit.permit_type_definition)

    # Score each dimension (0-100 each)
    d_inspection = _score_inspection_activity(permit, category, today)
    d_age = _score_age_staleness(permit, today)
    d_expiration = _score_expiration_proximity(permit, today)
    d_cost = _score_cost_tier(permit)
    d_category = _score_category_risk(category)

    # Weighted sum
    raw_score = (
        d_inspection * _W_INSPECTION
        + d_age * _W_AGE
        + d_expiration * _W_EXPIRATION
        + d_cost * _W_COST
        + d_category * _W_CATEGORY
    )
    score = int(round(_clamp(raw_score)))

    # Build dimension breakdown
    dimensions = {
        "inspection_activity": {"score": round(d_inspection, 1), "weight": _W_INSPECTION},
        "age_staleness": {"score": round(d_age, 1), "weight": _W_AGE},
        "expiration_proximity": {"score": round(d_expiration, 1), "weight": _W_EXPIRATION},
        "cost_tier": {"score": round(d_cost, 1), "weight": _W_COST},
        "category_risk": {"score": round(d_category, 1), "weight": _W_CATEGORY},
    }

    # Find top driver
    dim_contributions = {
        name: dim["score"] * dim["weight"]
        for name, dim in dimensions.items()
    }
    top_driver = max(dim_contributions, key=dim_contributions.get)  # type: ignore[arg-type]

    # Build explanation
    tier = _score_to_tier(score)
    explanation = _build_explanation(permit, category, dimensions, top_driver, tier, today)

    # Confidence
    confidence = "high"
    if permit.inspection_count == 0 and permit.status.lower() == "issued":
        confidence = "medium"  # No inspection data to validate

    return SeverityResult(
        score=score,
        tier=tier,
        dimensions=dimensions,
        top_driver=top_driver,
        explanation=explanation,
        confidence=confidence,
        category=category,
    )


def score_permits_batch(
    permits: list[PermitInput],
    today: date | None = None,
) -> list[SeverityResult]:
    """Score multiple permits. Convenience wrapper around score_permit."""
    return [score_permit(p, today=today) for p in permits]


# ---------------------------------------------------------------------------
# Explanation builder
# ---------------------------------------------------------------------------

_DIMENSION_LABELS = {
    "inspection_activity": "Inspection Activity",
    "age_staleness": "Age / Staleness",
    "expiration_proximity": "Expiration Proximity",
    "cost_tier": "Cost Tier",
    "category_risk": "Category Risk",
}

_TIER_DESCRIPTIONS = {
    "CRITICAL": "Requires immediate attention",
    "HIGH": "Significant risk factors present",
    "MEDIUM": "Moderate risk — monitor closely",
    "LOW": "Minor risk factors",
    "GREEN": "On track, no action needed",
}


def _build_explanation(
    permit: PermitInput,
    category: str,
    dimensions: dict,
    top_driver: str,
    tier: str,
    today: date,
) -> str:
    """Build a human-readable explanation of the score."""
    parts = [_TIER_DESCRIPTIONS.get(tier, "")]

    driver_label = _DIMENSION_LABELS.get(top_driver, top_driver)
    driver_score = dimensions[top_driver]["score"]
    parts.append(f"Top driver: {driver_label} ({driver_score:.0f}/100)")

    # Add context based on top driver
    if top_driver == "expiration_proximity" and permit.issued_date:
        cost = permit.revised_cost if permit.revised_cost is not None else (permit.estimated_cost or 0.0)
        validity = _validity_days(permit.permit_type_definition, cost)
        days_issued = (today - permit.issued_date).days
        expires_in = validity - days_issued
        if expires_in <= 0:
            parts.append(f"Permit expired {abs(expires_in)} days ago")
        else:
            parts.append(f"Permit expires in {expires_in} days")

    if top_driver == "age_staleness" and permit.filed_date:
        days_filed = (today - permit.filed_date).days
        parts.append(f"Filed {days_filed} days ago")
        if permit.status_date:
            days_since = (today - permit.status_date).days
            if days_since > 60:
                parts.append(f"No activity in {days_since} days")

    if top_driver == "inspection_activity":
        expected = EXPECTED_INSPECTIONS.get(category, 2.0)
        parts.append(f"{permit.inspection_count} inspections (expected ~{expected:.0f} for {category})")

    return ". ".join(parts)
