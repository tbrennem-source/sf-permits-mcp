"""Background task executor for non-blocking operations.

Uses a ThreadPoolExecutor to run tasks (email delivery, etc.) without
blocking the HTTP response. Pattern copied from web/plan_worker.py.
"""

import logging
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="bg-task")


def submit_task(fn, *args, **kwargs):
    """Submit a function to run in the background thread pool.

    Returns the Future object (caller can ignore it for fire-and-forget).
    """
    logger.debug("Background task submitted: %s", fn.__name__)
    return _executor.submit(fn, *args, **kwargs)
