"""Agency-to-station mapping for Sprint 58A.

Maps agency names returned by _determine_agency_routing() in predict_permits
to station codes used in station_velocity_v2 table.

Validated against actual station_velocity_v2 data (31 unique stations).
"""

from __future__ import annotations

# Full list of stations in station_velocity_v2 (validated 2026-02-26):
# BID-INSP, BLDG, BLDG-QC, CES, CON-BOND, CPB, CP-ZOC,
# DPW-BSM, DPW-BUF, EID-INSP, HEALTH, HEALTH-FD, HEALTH-HM,
# HEALTH-MB, HEALTH-MH, HIS, INTAKE, MECH, MECH-E, MECH-QC,
# PAD-STR, PERMIT-CTR, PID-INSP, PID-PC, PRE-BLDG, PW-DAC,
# REDEV, SFFD, SFFD-HQ, SFPUC, SFPUC-PRG

AGENCY_TO_STATIONS: dict[str, list[str]] = {
    # DBI Building — primary building plan review station
    "DBI (Building)": ["BLDG"],
    # Planning Department — zoning/occupancy review
    "Planning": ["CP-ZOC"],
    # SFFD — fire plan review (both field station and HQ)
    "SFFD (Fire)": ["SFFD", "SFFD-HQ"],
    # DPH Public Health — food facility, health, hazmat stations
    "DPH (Public Health)": ["HEALTH", "HEALTH-FD", "HEALTH-HM", "HEALTH-MH"],
    # DPW — Bureau of Street Use & Mapping
    "DPW/BSM": ["DPW-BSM", "DPW-BUF"],
    # SFPUC — utility/water connections
    "SFPUC": ["SFPUC", "SFPUC-PRG"],
    # DBI Mechanical/Electrical — HVAC, electrical, mechanical systems
    "DBI Mechanical/Electrical": ["MECH", "MECH-E"],
    # Historic preservation
    "Historic Preservation": ["HIS"],
    # Permit center (intake)
    "Permit Center": ["PERMIT-CTR", "INTAKE"],
}

# Reverse mapping: station code → agency display name
STATION_TO_AGENCY: dict[str, str] = {}
for _agency, _stations in AGENCY_TO_STATIONS.items():
    for _s in _stations:
        STATION_TO_AGENCY[_s] = _agency


def agencies_to_stations(agencies: list[str]) -> list[str]:
    """Convert a list of agency names to their station codes.

    Args:
        agencies: List of agency names from _determine_agency_routing()

    Returns:
        Deduplicated list of station codes in AGENCY_TO_STATIONS order.
    """
    seen: set[str] = set()
    result: list[str] = []
    for agency in agencies:
        for station in AGENCY_TO_STATIONS.get(agency, []):
            if station not in seen:
                seen.add(station)
                result.append(station)
    return result


def get_all_agency_names() -> list[str]:
    """Return all mapped agency names."""
    return list(AGENCY_TO_STATIONS.keys())


def get_all_station_codes() -> list[str]:
    """Return all mapped station codes (flat list, deduped)."""
    seen: set[str] = set()
    result: list[str] = []
    for stations in AGENCY_TO_STATIONS.values():
        for s in stations:
            if s not in seen:
                seen.add(s)
                result.append(s)
    return result
