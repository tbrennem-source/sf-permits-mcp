"""URL builder utility for property report inline source links.

Generates verified URLs for DBI permit tracker, complaint tracker,
SF Assessor, Planning Code (Municode), entity profiles, and Ethics registry.
"""

from urllib.parse import quote_plus


class ReportLinks:
    """Generates verified inline source links for report data points."""

    @staticmethod
    def permit(permit_number: str) -> str:
        """Internal permit search — home page with auto-submit."""
        return f"/?q={quote_plus(permit_number)}"

    @staticmethod
    def complaint(complaint_number: str) -> str:
        """Internal complaint search — home page with auto-submit."""
        return f"/?q={quote_plus(complaint_number)}"

    @staticmethod
    def parcel(block: str, lot: str) -> str:
        """SF Planning Property Information Map URL."""
        return f"https://sfplanninggis.org/pim/?search={block}%2F{lot}"

    @staticmethod
    def planning_code(section: str) -> str:
        """SF Planning Code section URL on Municode/amlegal."""
        SECTION_MAP = {
            "209.1": "0-0-0-17837",
            "311": "0-0-0-21240",
            "317": "0-0-0-21350",
            "260": "0-0-0-20490",
            "261.1": "0-0-0-20520",
            "249.94": "0-0-0-20058",
        }
        base = "https://codelibrary.amlegal.com/codes/san_francisco/latest/sf_planning"
        anchor = SECTION_MAP.get(section, "")
        return f"{base}/{anchor}" if anchor else base

    @staticmethod
    def entity(name: str) -> str:
        """sfpermits.ai entity profile URL."""
        return f"https://sfpermits-ai-production.up.railway.app/ask?q={quote_plus(name)}"

    @staticmethod
    def ethics_registry() -> str:
        """SF Ethics Commission permit consultant disclosure page."""
        return "https://sfethics.org/disclosures/permit-consultant-disclosure"

    @staticmethod
    def admin_bulletin(ab_number: str) -> str:
        """DBI Administrative Bulletin URL."""
        return "https://sf.gov/resource/2022/information-sheets-dbi"

    @staticmethod
    def state_legislation(bill_id: str) -> str:
        """California Legislature bill URL."""
        return f"https://leginfo.legislature.ca.gov/faces/billNavClient.xhtml?bill_id={bill_id}"

    @staticmethod
    def dbi_contact() -> str:
        """DBI general contact and services page."""
        return "https://sf.gov/departments/building-inspection"

    @staticmethod
    def planning_adu() -> str:
        """SF Planning ADU resource page."""
        return "https://sfplanning.org/accessory-dwelling-units"
