"""Routing progress tracker — Tier 0 operational intelligence.

Provides per-permit routing completion analysis from the addenda table
(3.9M plan review routing records). Used by:
- Intel panel (address card)
- Portfolio dashboard
- Intelligence engine
- Property report
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date

from src.db import BACKEND, query

logger = logging.getLogger(__name__)


def _ph() -> str:
    return "%s" if BACKEND == "postgres" else "?"


@dataclass
class StationStatus:
    """Status of a single routing station for a permit."""
    station: str
    department: str | None = None
    reviewer: str | None = None
    result: str | None = None
    finish_date: str | None = None
    arrive_date: str | None = None
    hold_description: str | None = None
    addenda_number: int | None = None
    step: int | None = None

    @property
    def is_complete(self) -> bool:
        return self.finish_date is not None

    @property
    def is_approved(self) -> bool:
        return bool(self.result and "approv" in self.result.lower())

    @property
    def has_comments(self) -> bool:
        return bool(self.result and "comment" in self.result.lower())

    @property
    def has_hold(self) -> bool:
        return bool(self.hold_description and self.hold_description.strip())

    @property
    def days_pending(self) -> int | None:
        """Days since arrival if not yet finished."""
        if self.is_complete or not self.arrive_date:
            return None
        try:
            arrive = date.fromisoformat(str(self.arrive_date)[:10])
            return (date.today() - arrive).days
        except (ValueError, TypeError):
            return None


@dataclass
class RoutingProgress:
    """Complete routing progress for a permit."""
    permit_number: str
    addenda_number: int | None = None
    total_stations: int = 0
    completed_stations: int = 0
    approved_stations: int = 0
    comments_issued: int = 0
    pending_stations: int = 0
    stations: list[StationStatus] = field(default_factory=list)
    latest_activity: StationStatus | None = None

    @property
    def completion_pct(self) -> int:
        if self.total_stations == 0:
            return 0
        return int(self.completed_stations * 100 / self.total_stations)

    @property
    def is_all_clear(self) -> bool:
        return self.total_stations > 0 and self.completed_stations == self.total_stations

    @property
    def pending_station_names(self) -> list[str]:
        return [s.station for s in self.stations if not s.is_complete]

    @property
    def stalled_stations(self) -> list[StationStatus]:
        """Stations pending >30 days with no hold."""
        return [s for s in self.stations
                if not s.is_complete
                and (s.days_pending or 0) > 30
                and not s.has_hold]

    @property
    def held_stations(self) -> list[StationStatus]:
        """Stations with unresolved holds."""
        return [s for s in self.stations
                if not s.is_complete and s.has_hold]


def get_routing_progress(permit_number: str) -> RoutingProgress | None:
    """Get full routing progress for a single permit.

    Looks at the latest addenda revision and returns a RoutingProgress
    with per-station detail. Returns None if no addenda data exists.
    """
    ph = _ph()

    try:
        # Get latest addenda revision number
        rev_rows = query(
            f"SELECT MAX(addenda_number) FROM addenda "
            f"WHERE application_number = {ph}",
            (permit_number,),
        )
        if not rev_rows or rev_rows[0][0] is None:
            return None
        rev_num = rev_rows[0][0]

        # Get all routing steps for this revision
        rows = query(
            f"SELECT station, department, plan_checked_by, review_results, "
            f"       finish_date, arrive, hold_description, addenda_number, step "
            f"FROM addenda "
            f"WHERE application_number = {ph} AND addenda_number = {ph} "
            f"ORDER BY step",
            (permit_number, rev_num),
        )
    except Exception:
        logger.debug("get_routing_progress failed for %s", permit_number, exc_info=True)
        return None

    if not rows:
        return None

    progress = RoutingProgress(
        permit_number=permit_number,
        addenda_number=rev_num,
    )

    latest_finish: str | None = None

    for row in rows:
        station_str = str(row[0] or "")
        s = StationStatus(
            station=station_str,
            department=str(row[1] or "") if row[1] else None,
            reviewer=str(row[2] or "") if row[2] else None,
            result=str(row[3] or "") if row[3] else None,
            finish_date=str(row[4])[:10] if row[4] else None,
            arrive_date=str(row[5])[:10] if row[5] else None,
            hold_description=str(row[6] or "") if row[6] else None,
            addenda_number=row[7],
            step=row[8],
        )
        progress.stations.append(s)
        progress.total_stations += 1

        if s.is_complete:
            progress.completed_stations += 1
            if s.is_approved:
                progress.approved_stations += 1
            if s.has_comments:
                progress.comments_issued += 1
            # Track latest activity
            fd = s.finish_date or ""
            if fd and (latest_finish is None or fd > latest_finish):
                latest_finish = fd
                progress.latest_activity = s
        else:
            progress.pending_stations += 1

    return progress


def get_routing_progress_batch(permit_numbers: list[str]) -> dict[str, RoutingProgress]:
    """Get routing progress for multiple permits at once.

    Returns dict mapping permit_number → RoutingProgress.
    Permits with no addenda data are omitted from the result.

    More efficient than calling get_routing_progress() per permit
    because it uses a single query to get all addenda data.
    """
    if not permit_numbers:
        return {}

    ph = _ph()
    placeholders = ",".join([ph] * len(permit_numbers))

    try:
        # Get latest addenda_number per permit in one query
        rev_rows = query(
            f"SELECT application_number, MAX(addenda_number) "
            f"FROM addenda "
            f"WHERE application_number IN ({placeholders}) "
            f"GROUP BY application_number",
            permit_numbers,
        )
    except Exception:
        logger.debug("get_routing_progress_batch rev query failed", exc_info=True)
        return {}

    if not rev_rows:
        return {}

    # Build (permit, rev) pairs for the main query
    permit_revs = {str(r[0]): r[1] for r in rev_rows if r[1] is not None}
    if not permit_revs:
        return {}

    # Build a query for all (permit, rev) pairs
    # We use OR conditions since each permit may have a different addenda_number
    conditions = []
    params = []
    for pnum, rev in permit_revs.items():
        conditions.append(f"(application_number = {ph} AND addenda_number = {ph})")
        params.extend([pnum, rev])

    where_clause = " OR ".join(conditions)

    try:
        rows = query(
            f"SELECT application_number, station, department, plan_checked_by, "
            f"       review_results, finish_date, arrive, hold_description, "
            f"       addenda_number, step "
            f"FROM addenda "
            f"WHERE {where_clause} "
            f"ORDER BY application_number, step",
            params,
        )
    except Exception:
        logger.debug("get_routing_progress_batch detail query failed", exc_info=True)
        return {}

    # Build RoutingProgress per permit
    results: dict[str, RoutingProgress] = {}

    for row in rows:
        pnum = str(row[0])
        if pnum not in results:
            results[pnum] = RoutingProgress(
                permit_number=pnum,
                addenda_number=permit_revs.get(pnum),
            )

        progress = results[pnum]
        s = StationStatus(
            station=str(row[1] or ""),
            department=str(row[2] or "") if row[2] else None,
            reviewer=str(row[3] or "") if row[3] else None,
            result=str(row[4] or "") if row[4] else None,
            finish_date=str(row[5])[:10] if row[5] else None,
            arrive_date=str(row[6])[:10] if row[6] else None,
            hold_description=str(row[7] or "") if row[7] else None,
            addenda_number=row[8],
            step=row[9],
        )
        progress.stations.append(s)
        progress.total_stations += 1

        if s.is_complete:
            progress.completed_stations += 1
            if s.is_approved:
                progress.approved_stations += 1
            if s.has_comments:
                progress.comments_issued += 1
            # Track latest activity
            if (progress.latest_activity is None
                    or (s.finish_date or "") > (progress.latest_activity.finish_date or "")):
                progress.latest_activity = s
        else:
            progress.pending_stations += 1

    return results
