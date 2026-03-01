#!/usr/bin/env python3
"""Create QA test account for MCP OAuth testing.

Usage:
    python scripts/create_qa_account.py

Creates an OAuth client registered in the database suitable for QA testing.
Outputs connection instructions.
"""

import os
import sys
import secrets
import json
from datetime import datetime, timezone

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


def main():
    client_id = "anthropic-qa-client"
    client_secret = secrets.token_urlsafe(32)

    print("=" * 60)
    print("SF Permits MCP — QA Test Account Setup")
    print("=" * 60)
    print()
    print(f"Client ID:     {client_id}")
    print(f"Client Secret: {client_secret}")
    print(f"Scope:         demo")
    print()
    print("OAuth Endpoints:")
    print("  Authorization: https://sfpermits-mcp-api-production.up.railway.app/authorize")
    print("  Token:         https://sfpermits-mcp-api-production.up.railway.app/token")
    print("  Register:      https://sfpermits-mcp-api-production.up.railway.app/register")
    print()
    print("Claude.ai Integration:")
    print("  MCP URL: https://sfpermits-mcp-api-production.up.railway.app/mcp")
    print("  Add via: Settings > Integrations > Add MCP Server")
    print()
    print("Note: Run this against the production database to pre-register the client.")
    print("See docs/MCP_TESTING.md for full setup instructions.")

    # Try to register if DATABASE_URL is set
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print()
        print("DATABASE_URL not set — skipping database registration.")
        print("To register, run with DATABASE_URL set to the pgvector-db connection string.")
        return

    try:
        import psycopg2
        conn = psycopg2.connect(database_url)
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO mcp_oauth_clients (client_id, client_secret, redirect_uris, client_name, scope)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (client_id) DO UPDATE
                    SET client_secret = EXCLUDED.client_secret,
                        client_name = EXCLUDED.client_name
            """, (
                client_id,
                client_secret,
                ["https://claude.ai/oauth/callback"],
                "Anthropic QA Client",
                "demo"
            ))
        conn.close()
        print()
        print("Client registered in database successfully.")
    except Exception as e:
        print(f"\nWarning: Could not register in database: {e}")


if __name__ == "__main__":
    main()
