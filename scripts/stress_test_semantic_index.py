#!/usr/bin/env python3
"""
Stress-test the semantic concept-to-source index.

Simulates 10 real-world queries (including Amy Lee's actual projects)
and evaluates whether the semantic index correctly identifies the right
source files and JSON paths for each query.

This tests Option A (concept-to-source mapping) as a search layer.
"""

import json
import re
from pathlib import Path

KNOWLEDGE_DIR = Path("/Users/timbrenneman/AIprojects/sf-permits-mcp/data/knowledge")

def load_semantic_index():
    with open(KNOWLEDGE_DIR / "tier1" / "semantic-index.json") as f:
        return json.load(f)

def match_concepts(query: str, index: dict, expand_related: bool = True) -> list:
    """
    Given a natural language query, match against concept aliases.
    Returns list of (concept_key, matched_alias, concept_data) tuples,
    sorted by alias length (longest match first = most specific).

    If expand_related=True, also includes 1-hop related_concepts from
    directly matched concepts (inference layer).
    """
    query_lower = query.lower()
    direct_matches = []
    matched_keys = set()

    for concept_key, concept_data in index["concepts"].items():
        # Check canonical name
        if concept_data["canonical_name"].lower() in query_lower:
            direct_matches.append((concept_key, concept_data["canonical_name"], concept_data))
            matched_keys.add(concept_key)
            continue

        # Check all aliases (longest first for specificity)
        sorted_aliases = sorted(concept_data["aliases"], key=len, reverse=True)
        for alias in sorted_aliases:
            if alias.lower() in query_lower:
                direct_matches.append((concept_key, alias, concept_data))
                matched_keys.add(concept_key)
                break  # Only match best alias per concept

    # Inference layer: expand via related_concepts (1-hop)
    inferred = []
    if expand_related:
        for concept_key, _, concept_data in direct_matches:
            for related_key in concept_data.get("related_concepts", []):
                if related_key not in matched_keys and related_key in index["concepts"]:
                    related_data = index["concepts"][related_key]
                    inferred.append((related_key, f"[inferred from {concept_key}]", related_data))
                    matched_keys.add(related_key)

    all_matches = direct_matches + inferred
    # Sort: direct matches first (by alias length), then inferred
    all_matches.sort(key=lambda x: (0 if not x[1].startswith("[inferred") else 1, -len(x[1])))
    return all_matches

def collect_sources(matches: list) -> list:
    """Collect and deduplicate all authoritative sources from matched concepts."""
    seen = set()
    sources = []
    for _, _, concept_data in matches:
        for source in concept_data.get("authoritative_sources", []):
            key = (source["file"], source.get("path", ""))
            if key not in seen:
                seen.add(key)
                sources.append(source)
    return sources

def verify_file_exists(source: dict) -> bool:
    """Check if the referenced source file actually exists."""
    filepath = KNOWLEDGE_DIR / source["file"]
    return filepath.exists()

def verify_json_path(source: dict) -> bool:
    """Check if the JSON path exists in the referenced file."""
    filepath = KNOWLEDGE_DIR / source["file"]
    if not filepath.exists():
        return False
    if not source["file"].endswith(".json"):
        return True  # Can't verify paths in non-JSON files
    if source.get("path") is None:
        return True  # No specific path to verify

    try:
        with open(filepath) as f:
            data = json.load(f)

        # Navigate the path
        path = source["path"]
        # Handle array indexing like "steps[2]" or "administrative_bulletins[AB-105]"
        parts = re.split(r'\.', path)
        current = data
        for part in parts:
            # Handle array index
            array_match = re.match(r'(\w+)\[(\d+)\]', part)
            dict_match = re.match(r'(\w+)\[([A-Z]+-\d+)\]', part)

            if array_match:
                key, idx = array_match.groups()
                if isinstance(current, dict) and key in current:
                    current = current[key]
                    if isinstance(current, list) and int(idx) < len(current):
                        current = current[int(idx)]
                    else:
                        return False
                else:
                    return False
            elif dict_match:
                key, search_val = dict_match.groups()
                if isinstance(current, dict) and key in current:
                    current = current[key]
                    if isinstance(current, list):
                        # Search by number field
                        found = False
                        for item in current:
                            if isinstance(item, dict) and item.get("number") == search_val:
                                found = True
                                break
                        return found
                    else:
                        return False
                else:
                    return False
            elif isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return False
        return True
    except Exception:
        return False


# =============================================================================
# TEST SCENARIOS
# =============================================================================

SCENARIOS = [
    {
        "id": 1,
        "name": "Amy's 199 Fremont — Office to Restaurant Conversion",
        "query": "I want to convert an office space at 199 Fremont Street to a food and beverage handling facility. What agencies need to review this and what are the fire department requirements?",
        "context": "This is Amy Lee's actual project: 199 Fremont, office → food/beverage handling, $2M + $800K deferred MEP.",
        "expected_concepts": ["change_of_use", "restaurant", "fire_department", "agency_routing", "commercial_kitchen_hood", "assembly_occupancy"],
        "expected_files": ["fire-code-key-sections.json", "G-20-routing.json", "planning-code-key-sections.json"],
        "must_find": ["A-2 occupancy threshold", "hood suppression", "SFFD review triggers"]
    },
    {
        "id": 2,
        "name": "Amy's 600 Battery — Priority Processing Office TI",
        "query": "We're doing a $14 million office tenant improvement at 600 Battery Street and want to use AB-004 priority processing. What are the fees and how does priority processing work?",
        "context": "Amy's actual project: 600 Battery St, $14.25M office TI with AB-004 priority processing.",
        "expected_concepts": ["commercial_ti", "priority_processing", "fee_calculation"],
        "expected_files": ["fee-tables.json", "administrative-bulletins-index.json"],
        "must_find": ["AB-004", "fee tiers", "plan review fees"]
    },
    {
        "id": 3,
        "name": "Amy's 1240 Fillmore — Seismic + Historic Windows",
        "query": "We're doing seismic strengthening and window replacement on a historic building at 1240 Fillmore. What reviews are needed and will the windows trigger historic preservation review?",
        "context": "Amy's actual project: 1240 Fillmore, $15M seismic strengthening, window replacement, ADA conversion.",
        "expected_concepts": ["seismic", "window_replacement", "historic_preservation", "disability_access"],
        "expected_files": ["planning-code-key-sections.json", "administrative-bulletins-index.json", "otc-criteria.json"],
        "must_find": ["Article 10", "Certificate of Appropriateness", "AB-094", "AB-082"]
    },
    {
        "id": 4,
        "name": "Amy's 3828 Jackson — Kitchen Remodel OTC",
        "query": "I want to remodel my kitchen in the Sunset district — move the sink, add an island, replace cabinets, add recessed lights. No structural changes. Can I do this over the counter?",
        "context": "Amy's actual project: 3828 Jackson St, $480K kitchen/bath/basement remodel, OTC.",
        "expected_concepts": ["kitchen_remodel", "otc_review", "fee_calculation"],
        "expected_files": ["otc-criteria.json", "fee-tables.json"],
        "must_find": ["OTC with plans", "one-hour rule", "plumbing fees"]
    },
    {
        "id": 5,
        "name": "Amy's Grand View — SFD to 2-Unit + ADU",
        "query": "I want to convert my single family home on Grand View to a 2-unit building and add an ADU. What's the process and timeline?",
        "context": "Amy's actual project: 107-109 Grand View, $1.195M SFD→2-unit with ADU.",
        "expected_concepts": ["adu", "inhouse_review", "planning_review", "section_311", "timeline"],
        "expected_files": ["otc-criteria.json", "planning-code-key-sections.json", "inhouse-review-process.json"],
        "must_find": ["NOT OTC", "Section 311", "ADU exempt from notification"]
    },
    {
        "id": 6,
        "name": "Amy's 799 Van Ness — Auto Sales to Gym",
        "query": "I want to convert an auto sales showroom at 799 Van Ness to a health studio and gym. What's the occupancy change and what agencies are involved?",
        "context": "Amy's actual project: 799 Van Ness, automobile sales → health studios & gym, $750K + $200K MEP.",
        "expected_concepts": ["change_of_use", "assembly_occupancy", "fire_department", "agency_routing"],
        "expected_files": ["fire-code-key-sections.json", "G-20-routing.json", "planning-code-key-sections.json"],
        "must_find": ["Group A-3", "occupancy change triggers SFFD"]
    },
    {
        "id": 7,
        "name": "Cross-Cutting Query: All Sprinkler Triggers",
        "query": "What are ALL the situations where automatic fire sprinklers are required in San Francisco?",
        "context": "Tests cross-file retrieval — sprinkler info spans fire-code, G-20, AB index, and fee tables.",
        "expected_concepts": ["sprinkler_required", "fire_department", "high_rise", "assembly_occupancy"],
        "expected_files": ["fire-code-key-sections.json", "administrative-bulletins-index.json", "G-20-routing.json"],
        "must_find": ["A-2 at 100 occupants", "high-rise >75ft", "SRO hotels", "AB-105", "e-bike charging 5+"]
    },
    {
        "id": 8,
        "name": "Fee Estimation: Restaurant Build-Out",
        "query": "How much will permit fees cost for a restaurant build-out valued at $500,000? Include plumbing, electrical, and SFFD fees.",
        "context": "Tests whether fee calculation pulls from multiple fee tables plus SFFD fee schedule.",
        "expected_concepts": ["fee_calculation", "restaurant"],
        "expected_files": ["fee-tables.json", "fire-code-key-sections.json"],
        "must_find": ["Table 1A-A", "Table 1A-C", "restaurant plumbing 6PA/6PB", "SFFD plan review fees"]
    },
    {
        "id": 9,
        "name": "Penalty Scenario: Work Without Permit",
        "query": "My contractor started work without pulling a permit. What's the penalty and how do I legalize it?",
        "context": "Tests penalty fee retrieval and code enforcement path.",
        "expected_concepts": ["penalty_fees", "fee_calculation"],
        "expected_files": ["fee-tables.json", "administrative-bulletins-index.json"],
        "must_find": ["9x permit issuance fee", "Table 1A-K", "AB-027"]
    },
    {
        "id": 10,
        "name": "Amy's 505 Mission Rock — New High-Rise Construction",
        "query": "We're building a 23-story, 233-unit residential tower at 505 Mission Rock. What are the fire code requirements, sprinkler requirements, and what agencies need to review?",
        "context": "Amy's largest project: 505 Mission Rock St, $67.25M, 23-story, 233 residential units.",
        "expected_concepts": ["high_rise", "sprinkler_required", "fire_alarm", "fire_department", "agency_routing", "controller_bond"],
        "expected_files": ["fire-code-key-sections.json", "G-20-routing.json", "fee-tables.json", "administrative-bulletins-index.json"],
        "must_find": [">75ft high-rise requirements", "ERRCS", "fire command center", "10+ units controller bond", "AB-083 tall building"]
    }
]

# =============================================================================
# RUN TESTS
# =============================================================================

def run_stress_test():
    index = load_semantic_index()

    print("=" * 80)
    print("SEMANTIC INDEX STRESS TEST")
    print(f"Testing {len(SCENARIOS)} scenarios against {len(index['concepts'])} concepts / {sum(len(c['aliases']) for c in index['concepts'].values())} aliases")
    print("=" * 80)

    results = []
    total_concept_hits = 0
    total_concept_expected = 0
    total_file_hits = 0
    total_file_expected = 0

    for scenario in SCENARIOS:
        print(f"\n{'─' * 80}")
        print(f"TEST {scenario['id']}: {scenario['name']}")
        print(f"Query: \"{scenario['query'][:100]}...\"" if len(scenario['query']) > 100 else f"Query: \"{scenario['query']}\"")
        print(f"Context: {scenario['context']}")
        print()

        # Run matching
        matches = match_concepts(scenario["query"], index)
        sources = collect_sources(matches)

        # Matched concepts
        matched_keys = [m[0] for m in matches]
        matched_aliases = [(m[0], m[1]) for m in matches]

        print(f"  MATCHED CONCEPTS ({len(matches)}):")
        for key, alias, _ in matches:
            print(f"    ✓ {key} (via \"{alias}\")")

        # Check expected concepts
        concept_hits = 0
        concept_misses = []
        for expected in scenario["expected_concepts"]:
            if expected in matched_keys:
                concept_hits += 1
            else:
                concept_misses.append(expected)

        total_concept_hits += concept_hits
        total_concept_expected += len(scenario["expected_concepts"])

        if concept_misses:
            print(f"\n  ✗ MISSED CONCEPTS: {concept_misses}")

        # Unexpected but matched (bonus — might be useful)
        unexpected = [k for k in matched_keys if k not in scenario["expected_concepts"]]
        if unexpected:
            print(f"  + BONUS CONCEPTS: {unexpected}")

        # Check file coverage
        source_files = set(s["file"].split("/")[-1] for s in sources)
        file_hits = 0
        file_misses = []
        for expected_file in scenario["expected_files"]:
            if expected_file in source_files:
                file_hits += 1
            else:
                file_misses.append(expected_file)

        total_file_hits += file_hits
        total_file_expected += len(scenario["expected_files"])

        print(f"\n  SOURCE FILES ({len(source_files)}):")
        for s in sources:
            exists = verify_file_exists(s)
            path_ok = verify_json_path(s)
            status = "✓" if exists and path_ok else ("⚠ path?" if exists else "✗ missing")
            print(f"    {status} {s['file']}")
            if s.get("path"):
                print(f"         → {s['path']}: {s['role'][:70]}")

        if file_misses:
            print(f"\n  ✗ MISSED FILES: {file_misses}")

        # Score
        concept_score = concept_hits / len(scenario["expected_concepts"]) * 100
        file_score = file_hits / len(scenario["expected_files"]) * 100

        print(f"\n  SCORE: Concepts {concept_hits}/{len(scenario['expected_concepts'])} ({concept_score:.0f}%) | Files {file_hits}/{len(scenario['expected_files'])} ({file_score:.0f}%)")

        results.append({
            "id": scenario["id"],
            "name": scenario["name"],
            "concept_score": concept_score,
            "file_score": file_score,
            "matched_concepts": len(matches),
            "missed_concepts": concept_misses,
            "bonus_concepts": unexpected,
            "source_files": len(source_files)
        })

    # Summary
    print(f"\n{'=' * 80}")
    print("OVERALL RESULTS")
    print(f"{'=' * 80}")

    avg_concept = total_concept_hits / total_concept_expected * 100
    avg_file = total_file_hits / total_file_expected * 100

    print(f"\nConcept Recall:  {total_concept_hits}/{total_concept_expected} ({avg_concept:.1f}%)")
    print(f"File Recall:     {total_file_hits}/{total_file_expected} ({avg_file:.1f}%)")

    perfect = sum(1 for r in results if r["concept_score"] == 100 and r["file_score"] == 100)
    print(f"Perfect Scores:  {perfect}/{len(results)}")

    print(f"\nPer-Scenario:")
    for r in results:
        status = "✓✓" if r["concept_score"] == 100 and r["file_score"] == 100 else "✓ " if r["concept_score"] >= 80 else "✗ "
        print(f"  {status} Test {r['id']}: {r['name'][:50]:50s} C:{r['concept_score']:3.0f}% F:{r['file_score']:3.0f}% ({r['matched_concepts']} concepts, {r['source_files']} files)")
        if r["missed_concepts"]:
            print(f"        Missed: {r['missed_concepts']}")

    # Return results for downstream use
    return results

if __name__ == "__main__":
    run_stress_test()
