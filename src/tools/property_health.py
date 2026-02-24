"""Tool: property_health — Return pre-computed property health from signal tables."""

import json
import logging

from src.db import get_connection, BACKEND

logger = logging.getLogger(__name__)

_PH = "%s" if BACKEND == "postgres" else "?"


def _exec_one(conn, sql, params=None):
    if BACKEND == "postgres":
        with conn.cursor() as cur:
            cur.execute(sql, params or [])
            return cur.fetchone()
    else:
        return conn.execute(sql, params or []).fetchone()


def _exec(conn, sql, params=None):
    if BACKEND == "postgres":
        with conn.cursor() as cur:
            cur.execute(sql, params or [])
            return cur.fetchall()
    else:
        return conn.execute(sql, params or []).fetchall()


async def property_health(
    block: str | None = None,
    lot: str | None = None,
    street_number: str | None = None,
    street_name: str | None = None,
) -> str:
    """Return pre-computed property health tier and signals.

    Looks up the property_health table (populated by nightly signal pipeline)
    to return the health tier, signal count, and individual signals for a property.

    Provide ONE of:
    - block + lot: parcel identifier (e.g., '3512' + '001')
    - street_number + street_name: address (e.g., '100' + 'Market')

    Returns health tier (high_risk/at_risk/behind/slower/on_track), signal details,
    and recommended actions.
    """
    has_parcel = bool(block and block.strip() and lot and lot.strip())
    has_address = bool(street_number and street_number.strip()
                       and street_name and street_name.strip())

    if not has_parcel and not has_address:
        return ("Please provide a block + lot (e.g., block='3512', lot='001') "
                "or street address (street_number='100', street_name='Market').")

    try:
        conn = get_connection()
    except Exception as e:
        logger.warning("DB connection failed in property_health: %s", e)
        return "Database unavailable — cannot look up property health."

    try:
        block_lot = None

        if has_parcel:
            block_lot = f"{block.strip()}/{lot.strip()}"
        elif has_address:
            # Look up block/lot from permits table
            sql = f"""
                SELECT DISTINCT block, lot
                FROM permits
                WHERE street_number = {_PH}
                  AND UPPER(street_name) = UPPER({_PH})
                  AND block IS NOT NULL AND lot IS NOT NULL
                LIMIT 1
            """
            row = _exec_one(conn, sql, [street_number.strip(), street_name.strip()])
            if row:
                block_lot = f"{row[0]}/{row[1]}"
            else:
                return f"No property found at **{street_number.strip()} {street_name.strip()}**."

        # Look up property_health
        sql = f"""
            SELECT tier, signal_count, at_risk_count, signals_json, computed_at
            FROM property_health
            WHERE block_lot = {_PH}
        """
        row = _exec_one(conn, sql, [block_lot])

        if not row:
            return (f"No health data for property **{block_lot}**. "
                    "This may mean the nightly signal pipeline hasn't run yet, "
                    "or this property has no signals (on_track).")

        tier, signal_count, at_risk_count, signals_json, computed_at = row

        # Format output
        lines = [f"# Property Health: {block_lot}\n"]

        tier_labels = {
            "high_risk": "HIGH RISK — Multiple independent risk signals",
            "at_risk": "AT RISK — Active risk signal(s)",
            "behind": "BEHIND — Falling behind, needs attention",
            "slower": "SLOWER — Minor concerns, informational",
            "on_track": "ON TRACK — No negative signals",
        }
        lines.append(f"**Tier:** {tier_labels.get(tier, tier)}")
        lines.append(f"**Signals:** {signal_count} total, {at_risk_count} at-risk")
        if computed_at:
            lines.append(f"**Last computed:** {str(computed_at)[:19]}")

        # Parse and display signals
        if signals_json:
            try:
                signals = json.loads(signals_json) if isinstance(signals_json, str) else signals_json
            except (json.JSONDecodeError, TypeError):
                signals = []

            if signals:
                lines.append("\n## Signals\n")
                lines.append("| Type | Severity | Permit | Detail |")
                lines.append("|------|----------|--------|--------|")
                for s in signals:
                    pn = s.get("permit", "—") or "—"
                    lines.append(
                        f"| {s.get('type', '')} | {s.get('severity', '')} "
                        f"| {pn} | {s.get('detail', '')} |"
                    )

        # Recommendations
        lines.append("\n## Recommended Actions\n")
        if tier == "high_risk":
            lines.append("- **Immediate review** — multiple independent risk factors converging")
            lines.append("- Check each signal for actionable next steps")
            lines.append("- Consider contacting property owner or expediter")
        elif tier == "at_risk":
            lines.append("- Review the active risk signal(s) and take corrective action")
            lines.append("- Schedule follow-up within 2 weeks")
        elif tier == "behind":
            lines.append("- Monitor at next monthly review")
            lines.append("- Check for pending station reviews or corrections")
        elif tier == "slower":
            lines.append("- No urgent action — include in quarterly review")
        else:
            lines.append("- Property is on track — no action needed")

        lines.append(f"\n---\n*Source: sfpermits.ai signal pipeline v2 ({BACKEND})*")
        return "\n".join(lines)

    finally:
        conn.close()
