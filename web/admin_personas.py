"""Admin persona definitions for QA impersonation.

Each persona injects a specific user state into the Flask session so Tim
can preview any user tier/state without creating real accounts.
"""

# ---------------------------------------------------------------------------
# Persona definitions
# ---------------------------------------------------------------------------

# Generate 12 placeholder address watches for power_user persona
_POWER_WATCHES = [
    {"watch_type": "address", "street_number": str(num), "street_name": street, "label": f"{num} {street}"}
    for num, street in [
        (1, "Market St"),
        (100, "Mission St"),
        (200, "Howard St"),
        (300, "Folsom St"),
        (400, "Bryant St"),
        (500, "Brannan St"),
        (600, "Townsend St"),
        (700, "King St"),
        (800, "Berry St"),
        (900, "Illinois St"),
        (1000, "3rd St"),
        (1100, "4th St"),
    ]
]

PERSONAS = [
    {
        "id": "anon_new",
        "label": "Anonymous New",
        "tier": "free",
        "watches": [],
        "search_history": [],
    },
    {
        "id": "anon_returning",
        "label": "Anonymous Returning",
        "tier": "free",
        "watches": [],
        "search_history": ["123 Main St", "555 Market St"],
    },
    {
        "id": "free_auth",
        "label": "Free Authenticated",
        "tier": "free",
        "watches": [],
        "search_history": ["Mission District permits"],
    },
    {
        "id": "beta_empty",
        "label": "Beta Empty",
        "tier": "beta",
        "watches": [],
        "search_history": [],
    },
    {
        "id": "beta_active",
        "label": "Beta Active (3 watches)",
        "tier": "beta",
        "watches": [
            {
                "watch_type": "address",
                "street_number": "1",
                "street_name": "Market St",
                "label": "1 Market St",
            },
            {
                "watch_type": "address",
                "street_number": "525",
                "street_name": "Market St",
                "label": "525 Market St",
            },
            {
                "watch_type": "address",
                "street_number": "3251",
                "street_name": "20th Ave",
                "label": "3251 20th Ave",
            },
        ],
        "search_history": ["seismic retrofit", "ADU permit cost"],
    },
    {
        "id": "power_user",
        "label": "Power User (12 watches)",
        "tier": "power",
        "watches": _POWER_WATCHES,
        "search_history": ["Tenderloin SRO", "Mission Victorian", "SOMA ADU"],
    },
    {
        "id": "admin_reset",
        "label": "Admin (reset)",
        "tier": "admin",
        "watches": [],
        "search_history": [],
    },
]

# Build a fast lookup dict by id
_PERSONAS_BY_ID = {p["id"]: p for p in PERSONAS}


def get_persona(persona_id: str) -> dict | None:
    """Look up a persona by id. Returns None if not found."""
    return _PERSONAS_BY_ID.get(persona_id)


def apply_persona(flask_session, persona: dict) -> None:
    """Inject persona state into the Flask session dict.

    Sets session keys:
    - "impersonating": True (so g.is_impersonating is set in _load_user)
    - "persona_id": persona["id"]
    - "persona_label": persona["label"]
    - "persona_tier": persona["tier"]
    - "persona_watches": persona["watches"]  (list of dicts)
    - "anon_searches": persona["search_history"]

    For "admin_reset" persona: clears all impersonation keys.
    Does NOT modify "user_id" — real auth session is preserved.
    """
    if persona["id"] == "admin_reset":
        # Clear all impersonation state
        for key in ("impersonating", "persona_id", "persona_label", "persona_tier",
                    "persona_watches", "anon_searches"):
            flask_session.pop(key, None)
        return

    flask_session["impersonating"] = True
    flask_session["persona_id"] = persona["id"]
    flask_session["persona_label"] = persona["label"]
    flask_session["persona_tier"] = persona["tier"]
    flask_session["persona_watches"] = persona["watches"]
    flask_session["anon_searches"] = persona["search_history"]
