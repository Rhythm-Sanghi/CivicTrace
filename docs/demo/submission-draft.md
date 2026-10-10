# CivicTrace: Official WarriorHacks 2.0 Submission Draft

## Project Title
**CivicTrace: A Public Record of Problems Worth Fixing**

## Short Pitch (Tagline)
An open-source, evidence-oriented civic infrastructure investigation system that replaces disappearing complaint tickets with an append-only cryptographic ledger and independent community resolution verification.

## The Problem
In civic administration across municipalities, citizen complaints suffer from an inherent conflict of interest: the department responsible for fixing an infrastructure problem is also the sole entity that decides when a ticket is closed. Consequently, complaints frequently disappear into a "Resolved" state while craters, water leaks, and broken streetlights persist on the street. Furthermore, duplicate reports submitted by neighbors are either ignored or treated as disconnected incidents, obscuring true civic urgency.

## What It Does
CivicTrace re-architects public problem tracking into an evidence-oriented investigation lifecycle:
1. **Deterministic Duplicate Correlation:** Clusters independent citizen observations near the same geographic coordinates (via Haversine proximity, vocabulary Jaccard similarity, and category weights) into unified public cases with preserved provenance.
2. **Explainable Civic Priority Engine:** Ranks infrastructure risks based on hazard category, independent corroboration count, and days unresolved with 100% transparent algorithmic reasons.
3. **The Independent Verification Gate:** Distinguishes between *Work Completion Claimed* and *Resolution Independently Verified*. Operators can claim repairs, but only local citizens can confirm resolution. Conflicting observations trigger a public dispute state.
4. **Append-Only Cryptographic Ledger:** Every status change, assignment, work claim, and citizen inspection is hashed into a sequential SHA-256 tamper-evident ledger.
5. **Chronic Recurrence Intelligence:** Tracks road and pipe repairs that fail within 30 days of closure, exposing recurring hotspots rather than resetting administrative memories.
6. **Portable Evidence Export:** Produces portable, manifest-signed ZIP evidence packages with an offline verification CLI for press and community advocates.

## Technologies Used
- **Backend:** Python 3.11, FastAPI, SQLAlchemy 2, Alembic, SQLite (local development) / PostgreSQL + PostGIS (production), Pydantic v2, Pytest.
- **Frontend:** React 19, TypeScript, Vite, React Router v7, TanStack Query, Lucide Icons, Modular CSS with Workshop + Gridline tokens.
- **Security & Integrity:** SHA-256 hash chaining, Canonical JSON serialization, bcrypt password hashing, JWT bearer auth with strict RBAC guards.

## Challenges Encountered
- Designing an append-only cryptographic hash chain that accounts for non-deterministic JSON serialization by establishing strict canonical key ordering and delimiter formats.
- Implementing an explainable, deterministic duplicate detection engine that operates entirely locally on standard CPU hardware without paid external LLMs or vendor lock-in.

## What Was Learned & Future Roadmap
- Transparent accountability systems require separating operator claims from citizen verification.
- Next milestones include offline-first PWA sync for field workers, municipal webhook integrations, and federated public checkpoints.

## Submission Links
- **GitHub Repository:** *(To be filled upon repository publication)*
- **Demonstration Video:** *(To be filled upon video recording)*
- **Live Local Demo:** `http://localhost:5173` (Frontend) & `http://localhost:8000/docs` (Interactive API)
