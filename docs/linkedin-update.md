# LinkedIn Profile Update

## Headline

Building AI-native software that builds itself | Creator of dforge | 21+ sprints of production agentic development

## About

I build production software with AI agents — not demos, not prototypes, but systems that handle real data at scale. My current project, sfpermits.ai, analyzes 13.3 million government records across 22 data sources to help permit expediters, architects, and homeowners navigate San Francisco's building permit system. It has 29 MCP tools, 3,327 automated tests, and runs a 12-step nightly pipeline that processes changes across 1.1 million permits.

The interesting part isn't the product — it's how it's built. I created dforge, a methodology framework for AI-native development. Every feature follows a specification-driven pipeline: behavioral scenarios define quality, multi-agent swarms build in parallel, automated QA gates enforce standards, and governance documents (CANON.md, PRINCIPALS.md) control agent behavior. This isn't "developer uses AI tools." It's a fundamentally different way of building software where AI agents are team members with specifications, not autocomplete engines.

My thesis: AI development needs methodology the same way software development needed Agile. The gap between "AI can write code" and "AI can build production systems" is entirely a methodology gap — specifications, governance, quality gates, and operational discipline. dforge is my answer to that gap, born from 21+ sprints of learning what works and what doesn't when you treat AI agents as collaborators.

I'm looking to connect with teams building at the intersection of AI and production software engineering — especially those who've moved past the demo stage and are dealing with the real challenges of AI-assisted development at scale.

## Experience Entry

### AI-Native Software Engineer & Framework Creator

**Period:** February 2026 – Present

**sfpermits.ai — San Francisco Building Permit Intelligence Platform**

- Built a production permit intelligence platform analyzing 13.3M+ records from 22 government SODA API sources, deployed on Railway with Flask + PostgreSQL + Claude Vision
- Designed and implemented a 5-step entity resolution pipeline that resolved 1.8M raw contacts into 1M unique entities with 576K relationship edges
- Created 29 MCP tools spanning 7 functional domains: live API queries, entity networks, knowledge-based permit prediction, AI vision plan analysis, and 3.9M-record addenda routing search
- Built a 4-tier knowledge base from 51 DBI info sheets, 47 administrative bulletins, and the complete SF Planning Code (12.6MB) — structured into 47 JSON files with an 86-concept semantic index
- Maintained 3,327 automated tests across 21+ production sprints with zero-downtime deployments

**dforge — AI-Native Development Framework**

- Created a methodology framework for human-AI collaborative development with 12 templates, 3 frameworks, and 16 lessons learned from production experience
- Designed the Black Box Protocol: spec in → working software out → QA gate → deploy, enforced by CI hooks that block incomplete deliverables
- Developed multi-agent swarm coordination patterns: 4+ parallel Claude Code agents per sprint, isolated file domains, sequential merge validation
- Defined behavioral scenarios as quality gates: 73 approved scenarios governing system behavior, reviewed from 102 candidates through a specification-driven governance process
- Published the Five Levels of AI-Native Development maturity model and 8-dimension project health scoring system
