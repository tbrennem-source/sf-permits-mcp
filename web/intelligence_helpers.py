# web/intelligence_helpers.py (STUB — will be replaced by T1-B's real version)
"""Synchronous wrappers for intelligence tool calls used in property reports.

This stub returns None/empty so the report assembler can import safely without
depending on T1-B's real implementation being merged first.
"""


def get_stuck_diagnosis_sync(permit_number):
    """Return stuck diagnosis for a permit, or None if unavailable."""
    return None


def get_delay_cost_sync(permit_type, monthly_cost, neighborhood=None):
    """Return delay cost estimate for a permit type, or None if unavailable."""
    return None


def get_similar_projects_sync(permit_type, neighborhood=None, cost=None):
    """Return list of similar projects, or empty list if unavailable."""
    return []
