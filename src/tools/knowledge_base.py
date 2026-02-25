"""Shared knowledge base loader for SF permitting decision tools.

Loads all structured JSON knowledge files once at first access.
All Phase 2.75 tools import from this module.
"""

import json
import os
from pathlib import Path
from functools import lru_cache


def _knowledge_dir() -> Path:
    """Resolve the knowledge directory path."""
    # Try relative to this file first (src/tools/knowledge_base.py -> data/knowledge)
    base = Path(__file__).parent.parent.parent / "data" / "knowledge"
    if base.exists():
        return base
    # Fall back to env var
    env_path = os.environ.get("SF_PERMITS_KNOWLEDGE_DIR")
    if env_path:
        return Path(env_path)
    raise FileNotFoundError(
        "Cannot find data/knowledge/ directory. "
        "Set SF_PERMITS_KNOWLEDGE_DIR environment variable."
    )


def _load_json(path: Path) -> dict | list:
    """Load a JSON file, returning empty dict on failure."""
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Warning: Could not load {path}: {e}")
        return {}


@lru_cache(maxsize=1)
def get_knowledge_base() -> "KnowledgeBase":
    """Get the singleton KnowledgeBase instance."""
    return KnowledgeBase(_knowledge_dir())


class KnowledgeBase:
    """Loads and provides access to all structured knowledge files."""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        tier1 = data_dir / "tier1"

        # Core decision tree
        self.decision_tree = _load_json(data_dir / "decision-tree-draft.json")

        # Step backing data
        self.routing_matrix = _load_json(tier1 / "G-20-routing.json")
        self.otc_criteria = _load_json(tier1 / "otc-criteria.json")
        self.fee_tables = _load_json(tier1 / "fee-tables.json")
        self.forms_taxonomy = _load_json(tier1 / "permit-forms-taxonomy.json")
        self.completeness_checklist = _load_json(tier1 / "completeness-checklist.json")
        self.semantic_index = _load_json(tier1 / "semantic-index.json")
        self.fire_code = _load_json(tier1 / "fire-code-key-sections.json")
        self.planning_code = _load_json(tier1 / "planning-code-key-sections.json")
        self.inhouse_review = _load_json(tier1 / "inhouse-review-process.json")
        self.epr_requirements = _load_json(tier1 / "epr-requirements.json")
        self.decision_tree_gaps = _load_json(tier1 / "decision-tree-gaps.json")

        # Compliance knowledge (Phase 2.6 supplement)
        self.title24 = _load_json(tier1 / "title24-energy-compliance.json")
        self.green_building = _load_json(tier1 / "green-building-requirements.json")
        self.dph_food = _load_json(tier1 / "dph-food-facility-requirements.json")
        self.ada_accessibility = _load_json(tier1 / "ada-accessibility-requirements.json")

        # Phase 2.75d — G-01 signature requirements + G-25 restaurant guide
        self.plan_signatures = _load_json(tier1 / "plan-signature-requirements.json")
        self.restaurant_guide = _load_json(tier1 / "restaurant-permit-guide.json")

        # Phase 2.75e — DA-12/DA-13 accessibility + S-09 Earthquake Brace+Bolt
        self.earthquake_brace_bolt = _load_json(tier1 / "earthquake-brace-bolt.json")

        # Phase E — Owner Mode remediation roadmap
        self.remediation_roadmap = _load_json(tier1 / "remediation-roadmap.json")

        # Building Code deep-dive — full SFBC ingestion from tier4
        self.permit_expiration_rules = _load_json(tier1 / "permit-expiration-rules.json")
        self.permit_requirements = _load_json(tier1 / "permit-requirements.json")
        self.inspections_process = _load_json(tier1 / "inspections-process.json")
        self.certificates_occupancy = _load_json(tier1 / "certificates-occupancy.json")
        self.enforcement_process = _load_json(tier1 / "enforcement-process.json")
        self.appeals_bodies = _load_json(tier1 / "appeals-bodies.json")

        # FS-Series Fire Safety Info Sheets (Session 24)
        self.fire_safety_info_sheets = _load_json(tier1 / "fire-safety-info-sheets.json")

        # DBI Permit Services — sf.gov scraped content (Session 22.5)
        self.otc_step_by_step = _load_json(tier1 / "otc-step-by-step.json")
        self.adu_programs = _load_json(tier1 / "adu-programs.json")
        self.pre_application_meetings = _load_json(tier1 / "pre-application-meetings.json")
        self.recheck_resubmission = _load_json(tier1 / "recheck-resubmission-process.json")
        self.permit_issuance_documents = _load_json(tier1 / "permit-issuance-documents.json")
        self.geotechnical_requirements = _load_json(tier1 / "geotechnical-requirements.json")
        self.construction_types = _load_json(tier1 / "construction-types.json")
        self.floodplain_soft_story = _load_json(tier1 / "floodplain-soft-story.json")
        self.sf_2025_code_amendments = _load_json(tier1 / "sf-2025-code-amendments.json")

        # Sprint 56B — Trade permits, street use, housing, reference tables knowledge
        self.trade_permits = _load_json(tier1 / "trade-permits.json")
        self.street_use_permits = _load_json(tier1 / "street-use-permits.json")
        self.housing_development = _load_json(tier1 / "housing-development.json")
        self.reference_tables_knowledge = _load_json(tier1 / "reference-tables.json")

        # Build keyword index from semantic index
        self._keyword_index = self._build_keyword_index()

    def _build_keyword_index(self) -> dict[str, list[str]]:
        """Build a mapping from keyword -> list of concept names.

        Uses the semantic-index.json aliases to match user descriptions
        to knowledge concepts. This replaces hardcoded keyword dicts.
        """
        index: dict[str, list[str]] = {}
        concepts = self.semantic_index.get("concepts", {})
        for concept_name, concept_data in concepts.items():
            if not isinstance(concept_data, dict):
                continue  # skip comment entries like _comment_tier0
            aliases = concept_data.get("aliases", [])
            for alias in aliases:
                key = alias.lower().strip()
                if key not in index:
                    index[key] = []
                index[key].append(concept_name)
        return index

    def match_concepts(self, text: str) -> list[str]:
        """Match a text description against semantic index aliases.

        Returns a list of matched concept names, deduplicated, ordered by
        relevance score (highest first).
        """
        scored = self.match_concepts_scored(text)
        return [name for name, _score in scored]

    def match_concepts_scored(self, text: str) -> list[tuple[str, float]]:
        """Match text against semantic index aliases with relevance scoring.

        Returns list of (concept_name, score) tuples sorted by score descending.

        Scoring factors:
        - Longer alias matches score higher (specificity)
        - Multi-word alias matches score higher than single-word
        - Multiple distinct alias matches for the same concept boost its score
        - Aliases that are whole words (not substrings of longer words) get a bonus
        """
        import re

        text_lower = text.lower()
        # Track per-concept: list of (alias_length, is_whole_word)
        concept_hits: dict[str, list[tuple[int, bool]]] = {}

        for keyword, concepts in self._keyword_index.items():
            if keyword in text_lower:
                # Check if match is a whole-word boundary match
                # Build pattern: word boundary on each side of the keyword
                pattern = r'(?:^|[\s,;.!?()\-/])' + re.escape(keyword) + r'(?:$|[\s,;.!?()\-/])'
                is_whole_word = bool(re.search(pattern, text_lower))

                for c in concepts:
                    if c not in concept_hits:
                        concept_hits[c] = []
                    concept_hits[c].append((len(keyword), is_whole_word))

        # Score each concept
        scored: list[tuple[str, float]] = []
        for concept_name, hits in concept_hits.items():
            # Base score: longest matching alias length (normalized)
            max_alias_len = max(h[0] for h in hits)
            specificity = max_alias_len / 20.0  # Normalize: 20-char alias = 1.0

            # Bonus: number of distinct alias matches (breadth of match)
            breadth_bonus = min(len(hits) * 0.15, 0.6)  # Cap at 0.6

            # Bonus: whole-word matches vs substring matches
            whole_word_hits = sum(1 for h in hits if h[1])
            whole_word_bonus = whole_word_hits * 0.2

            # Bonus: multi-word aliases (more specific)
            multi_word_hits = sum(1 for h in hits if ' ' in self._keyword_index
                                  and h[0] > 3)
            # Simpler: just check if longest match has spaces
            has_multiword = any(
                alias for alias, concepts in self._keyword_index.items()
                if alias in text_lower and concept_name in concepts and ' ' in alias
            )
            multiword_bonus = 0.3 if has_multiword else 0.0

            score = specificity + breadth_bonus + whole_word_bonus + multiword_bonus
            scored.append((concept_name, round(score, 3)))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored

    def get_step_confidence(self, step: int) -> str:
        """Get the confidence level for a decision tree step from gaps analysis."""
        steps = self.decision_tree_gaps.get("steps", [])
        for s in steps:
            if s.get("step") == step:
                return s.get("confidence", "unknown")
        return "unknown"


# --- Source citation system ---

# Maps knowledge attribute names to official source info
SOURCE_REGISTRY: dict[str, dict[str, str]] = {
    "decision_tree": {
        "label": "DBI Decision Tree (7-step permit pathway)",
        "url": "https://sf.gov/departments/building-inspection/permits",
    },
    "routing_matrix": {
        "label": "DBI Info Sheet G-20: Routing Matrix",
        "url": "https://sf.gov/resource/2022/information-sheets-dbi",
    },
    "otc_criteria": {
        "label": "DBI OTC Permit Criteria (55 project type classifications)",
        "url": "https://sf.gov/resource/2022/information-sheets-dbi",
    },
    "fee_tables": {
        "label": "DBI Fee Schedule G-13 (Tables 1A-A through 1A-S, eff. 9/1/2025)",
        "url": "https://sf.gov/resource/2022/information-sheets-dbi",
    },
    "forms_taxonomy": {
        "label": "DBI Permit Forms Taxonomy",
        "url": "https://sf.gov/departments/building-inspection/permits",
    },
    "completeness_checklist": {
        "label": "DBI 13-Section Completeness Checklist",
        "url": "https://sf.gov/departments/building-inspection/permits",
    },
    "fire_code": {
        "label": "SF Fire Code — Tables 107-B, 107-C (SFFD fees)",
        "url": "https://codelibrary.amlegal.com/codes/san_francisco/latest/sf_fire/0-0-0-2",
    },
    "planning_code": {
        "label": "SF Planning Code (zoning, CU, Section 311)",
        "url": "https://codelibrary.amlegal.com/codes/san_francisco/latest/sf_planning/",
    },
    "inhouse_review": {
        "label": "DBI In-House Review Process Guide",
        "url": "https://sf.gov/departments/building-inspection/permits",
    },
    "epr_requirements": {
        "label": "DBI Electronic Plan Review (EPR) Requirements",
        "url": "https://sf.gov/departments/building-inspection/permits",
    },
    "title24": {
        "label": "DBI Title-24 Energy Compliance (M-03, M-04, M-06, M-08)",
        "url": "https://sf.gov/resource/2022/information-sheets-dbi",
    },
    "green_building": {
        "label": "AB-093: Green Building Requirements (GS form logic, LEED/GreenPoint, compliance methods)",
        "url": "https://codelibrary.amlegal.com/codes/san_francisco/latest/sf_building/0-0-0-89498",
    },
    "dph_food": {
        "label": "DPH Food Facility Construction Requirements (22 checks)",
        "url": "https://www.sfdph.org/dph/EH/Food/default.asp",
    },
    "ada_accessibility": {
        "label": "DBI Info Sheets DA-02, DA-12, DA-13 (CBC 11B Accessibility)",
        "url": "https://sf.gov/resource/2022/information-sheets-dbi",
    },
    "plan_signatures": {
        "label": "DBI Info Sheet G-01: Signature on Plans (4 status categories)",
        "url": "https://sf.gov/resource/2022/information-sheets-dbi",
    },
    "restaurant_guide": {
        "label": "DBI Info Sheet G-25: Restaurant Building Permit Requirements",
        "url": "https://sf.gov/resource/2022/information-sheets-dbi",
    },
    "earthquake_brace_bolt": {
        "label": "DBI Info Sheet S-09: Earthquake Brace+Bolt (CEBC A3)",
        "url": "https://sf.gov/resource/2022/information-sheets-dbi",
    },
    "remediation_roadmap": {
        "label": "SF Permits Remediation Roadmap (risk-to-action mapping)",
        "url": "https://sfpermits-ai-production.up.railway.app/report",
    },
    "permit_expiration_rules": {
        "label": "SFBC Section 106A.4.4 — Permit Expiration Rules (Table A, Table B)",
        "url": "https://codelibrary.amlegal.com/codes/san_francisco/latest/sf_building/",
    },
    "permit_requirements": {
        "label": "SFBC Section 106A.1–106A.3 — Permit Requirements & Exemptions",
        "url": "https://codelibrary.amlegal.com/codes/san_francisco/latest/sf_building/",
    },
    "inspections_process": {
        "label": "SFBC Section 109A — Inspections (9 stages, reinspection rules)",
        "url": "https://codelibrary.amlegal.com/codes/san_francisco/latest/sf_building/",
    },
    "certificates_occupancy": {
        "label": "SFBC Section 110A — Certificates of Occupancy & Apartment Licenses",
        "url": "https://codelibrary.amlegal.com/codes/san_francisco/latest/sf_building/",
    },
    "enforcement_process": {
        "label": "SFBC Sections 102A.8–102A.12 — Enforcement, NOVs, Penalties",
        "url": "https://codelibrary.amlegal.com/codes/san_francisco/latest/sf_building/",
    },
    "appeals_bodies": {
        "label": "SFBC Sections 103A–105A — Appeals Bodies, Vacant Building Registration",
        "url": "https://codelibrary.amlegal.com/codes/san_francisco/latest/sf_building/",
    },
    "otc_step_by_step": {
        "label": "DBI OTC Step-by-Step Guides (residential interior, exterior, commercial)",
        "url": "https://www.sf.gov/step-by-step--get-otc-permit-your-interior-residential-remodel/",
    },
    "adu_programs": {
        "label": "DBI ADU Programs (new ADU, detached pre-approval, unit legalization)",
        "url": "https://www.sf.gov/topics--accessory-dwelling-unit-adu/",
    },
    "pre_application_meetings": {
        "label": "DBI Pre-Application Meetings (binding code interpretations)",
        "url": "https://www.sf.gov/schedule-pre-application-meeting/",
    },
    "recheck_resubmission": {
        "label": "DBI Recheck/Resubmission Process (plan rechecks, streamlined housing, affordable)",
        "url": "https://www.sf.gov/recheck-plans-OTC-building-permit-application/",
    },
    "permit_issuance_documents": {
        "label": "DBI Permit Issuance Documents & Plans Requirements",
        "url": "https://www.sf.gov/gather-documents-your-building-permit-issuance/",
    },
    "geotechnical_requirements": {
        "label": "DBI Geotechnical Reports & Third-Party Engineering Review",
        "url": "https://www.sf.gov/check-if-your-project-requires-a-geotechnical-report-or-third-party-engineering-review/",
    },
    "construction_types": {
        "label": "DBI Building Construction Type Definitions (Type I-V)",
        "url": "https://www.sf.gov/information--building-construction-type-definitions/",
    },
    "floodplain_soft_story": {
        "label": "DBI Floodplain Management & Soft Story Retrofit",
        "url": "https://www.sf.gov/comply-floodplain-management-requirements/",
    },
    "sf_2025_code_amendments": {
        "label": "2025 SF Code Amendments (effective Jan 1, 2026)",
        "url": "https://www.sf.gov/resource--2022--current-san-francisco-building-codes/",
    },
    "duckdb_permits": {
        "label": "SF Open Data — Building Permits (1.1M+ records via SODA API)",
        "url": "https://data.sfgov.org/Housing-and-Buildings/Building-Permits/i98e-djp9",
    },
    "duckdb_inspections": {
        "label": "SF Open Data — Housing Inspections (671K+ records)",
        "url": "https://data.sfgov.org/Housing-and-Buildings/Housing-Complaints-and-Inspection-Data/gm2e-bten",
    },
}


def format_sources(source_keys: list[str]) -> str:
    """Format a Sources section for tool output.

    Args:
        source_keys: List of SOURCE_REGISTRY keys used in generating the output.

    Returns:
        Formatted markdown Sources section with clickable links.
    """
    seen = set()
    lines = ["\n---\n## Sources\n"]
    for key in source_keys:
        if key in seen:
            continue
        seen.add(key)
        info = SOURCE_REGISTRY.get(key)
        if info:
            lines.append(f"- [{info['label']}]({info['url']})")
    if len(lines) == 1:
        return ""  # No valid sources
    lines.append("")  # trailing newline
    return "\n".join(lines)
