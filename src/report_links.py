"""URL builder utility for property report inline source links.

Generates verified URLs for DBI permit tracker, complaint tracker,
SF Assessor, Planning Code (Municode), entity profiles, and Ethics registry.
"""

from urllib.parse import quote_plus


class ReportLinks:
    """Generates verified inline source links for report data points."""

    @staticmethod
    def permit(permit_number: str) -> str:
        """DBI Permit Tracker URL."""
        return f"https://dbiweb02.sfgov.org/dbipts/default.aspx?page=Permit&PermitNumber={permit_number}"

    @staticmethod
    def complaint(complaint_number: str) -> str:
        """DBI Complaint Tracker URL."""
        return f"https://dbiweb02.sfgov.org/dbipts/default.aspx?page=Complaint&ComplaintNumber={complaint_number}"

    @staticmethod
    def parcel(block: str, lot: str) -> str:
        """SF Assessor-Recorder property page URL."""
        return f"https://sfassessor.org/property-information?block={block}&lot={lot}"

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
