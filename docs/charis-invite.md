# Beta Invite: Charis Kaskiris (GridCARE)

## Invite Code
`friends-gridcare`

## Setup
Add to Railway env var INVITE_CODES (comma-separated):
```bash
railway variable set INVITE_CODES="existing-codes,friends-gridcare"
```

## Message Draft

Hey Charis,

I built something I think you'll find interesting — **sfpermits.ai**, an AI-powered San Francisco building permit intelligence platform.

**What it does:**
- **MCP Architecture**: 30 tools exposed over Streamable HTTP — the same protocol Claude uses natively. You can plug it into any MCP-compatible client.
- **Agentic AI builds**: The entire codebase is built using multi-agent swarm sessions with a Black Box Protocol (automated QA, behavioral scenarios, visual review).
- **Deep data**: 1.1M+ permits, 3.9M review routing records, 1M resolved entities, 576K relationship edges — all queryable in real time.
- **Transparent methodology**: See [/methodology](https://sfpermits.ai/methodology) — 3,000+ words explaining exactly how we calculate timelines, fees, and risk scores.

**Energy-relevant demo**: Search for addresses with solar permits. For example, "75 Robin Hood Dr" has solar permit S20251030283 — you can see the full permit history, inspection timeline, and contractor network.

**The depth**: 22 SODA datasets (13.3M records cataloged), nightly pipeline refresh, 47 curated knowledge base files, hybrid RAG retrieval with 1,035 chunks.

Your invite code is `friends-gridcare`. Sign up at:
https://sfpermits.ai/auth/login

I'd love your feedback — especially on the data architecture and how we're using AI for prediction and analysis.

— Tim

## Test on Staging
1. Go to https://sfpermits-ai-staging-production.up.railway.app/auth/login
2. Enter new email, use code `friends-gridcare`
3. Verify account created with correct tier
4. Note: INVITE_CODES env var must include `friends-gridcare` on staging too
