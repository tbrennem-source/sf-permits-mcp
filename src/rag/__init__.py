"""RAG knowledge retrieval system.

Three-tier architecture:
- official: codes, DBI pages, info sheets, ABs (trust_weight=1.0)
- amy: tribal knowledge corrections (trust_weight=0.9)  -- Phase 2
- learned: patterns from draft edits (trust_weight=0.7)  -- Phase 3
"""
