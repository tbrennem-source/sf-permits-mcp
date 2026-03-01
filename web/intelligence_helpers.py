# web/intelligence_helpers.py
# STUB — will be replaced by T1-B's real implementation
# These functions provide sync wrappers for intelligence tool calls used in analyze().

def get_stuck_diagnosis_sync(permit_number):
    """Return stuck diagnosis dict for a permit number, or None if unavailable."""
    return None


def get_delay_cost_sync(permit_type, monthly_cost, neighborhood=None):
    """Return delay cost analysis dict, or None if unavailable."""
    return None


def get_similar_projects_sync(permit_type, neighborhood=None, cost=None):
    """Return list of similar project dicts, or [] if unavailable."""
    return []
