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
        self.dph_food = _load_json(tier1 / "dph-food-facility-requirements.json")
        self.ada_accessibility = _load_json(tier1 / "ada-accessibility-requirements.json")

        # Phase 2.75d — G-01 signature requirements + G-25 restaurant guide
        self.plan_signatures = _load_json(tier1 / "plan-signature-requirements.json")
        self.restaurant_guide = _load_json(tier1 / "restaurant-permit-guide.json")

        # Phase 2.75e — DA-12/DA-13 accessibility + S-09 Earthquake Brace+Bolt
        self.earthquake_brace_bolt = _load_json(tier1 / "earthquake-brace-bolt.json")

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
            aliases = concept_data.get("aliases", [])
            for alias in aliases:
                key = alias.lower().strip()
                if key not in index:
                    index[key] = []
                index[key].append(concept_name)
        return index

    def match_concepts(self, text: str) -> list[str]:
        """Match a text description against semantic index aliases.

        Returns a list of matched concept names, deduplicated.
        """
        text_lower = text.lower()
        matched = set()
        for keyword, concepts in self._keyword_index.items():
            if keyword in text_lower:
                for c in concepts:
                    matched.add(c)
        return sorted(matched)

    def get_step_confidence(self, step: int) -> str:
        """Get the confidence level for a decision tree step from gaps analysis."""
        steps = self.decision_tree_gaps.get("steps", [])
        for s in steps:
            if s.get("step") == step:
                return s.get("confidence", "unknown")
        return "unknown"
