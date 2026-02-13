"""Tool: get_permit_details — Get full details for a specific permit."""

from src.soda_client import SODAClient
from src.formatters import format_permit_detail

ENDPOINT_ID = "i98e-djp9"  # Building Permits


async def get_permit_details(permit_number: str) -> str:
    """Get full details for a specific SF building permit.

    Args:
        permit_number: The permit number (e.g., '202301015555')

    Returns:
        Complete permit record with all available fields, organized by category.
    """
    client = SODAClient()
    try:
        results = await client.query(
            endpoint_id=ENDPOINT_ID,
            where=f"permit_number='{_escape(permit_number)}'",
            limit=5,  # May have multiple records (different addresses)
        )
        if not results:
            return f"No permit found with number '{permit_number}'."

        if len(results) == 1:
            return format_permit_detail(results[0])

        # Multiple records — show primary address first, note others
        primary = [r for r in results if r.get("primary_address_flag") == "Y"]
        if primary:
            output = format_permit_detail(primary[0])
            if len(results) > 1:
                output += (
                    f"\n\n*Note: This permit has {len(results)} address records. "
                    f"Showing primary address.*"
                )
            return output

        # No primary flag — show first result
        output = format_permit_detail(results[0])
        if len(results) > 1:
            output += (
                f"\n\n*Note: This permit has {len(results)} address records. "
                f"Showing first result.*"
            )
        return output
    finally:
        await client.close()


def _escape(value: str) -> str:
    """Basic SoQL string escaping."""
    return value.replace("'", "''").replace("\\", "\\\\")
