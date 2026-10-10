# Changelog

All notable changes to CivicTrace are documented in this file.

## [1.1.0] - 2026-10-10
### Hardened & Verified
- Multi-tier resolution governance policy:
  - Enforced 2-confirmation citizen quorum for auto-resolving uncontested cases.
  - Identity deduplication preventing multiple verification submissions by the same user/pseudonym.
  - Contradictory dispute protection: any dispute observation immediately sets state to `DISPUTED`.
  - Reviewer dispute mediation & rework ordering workflow in case details dossier.
- File upload security hardening: MIME validation whitelist (JPEG, PNG, WebP, PDF), 10MB size ceiling, SHA-256 evidence hashing, and ledger tracking.
- Zip Slip and path traversal protection in evidence package export and extraction.
- Production startup security check: safe termination if default dev secrets are detected in `ENVIRONMENT=production`.
- Alembic database migration management added (`migrations/`) for declarative PostgreSQL / PostGIS portability.
- Modernized Pydantic v2 schemas (`ConfigDict(from_attributes=True)`), eliminating legacy deprecations.
- Frontend test suite with Vitest and React Testing Library (`vitest.config.ts`).
- Automated headless browser E2E test suite (`scripts/run_browser_e2e.py`) via Playwright, capturing 6 genuine application screenshots.
- CI pipeline workflow updated (`.github/workflows/ci.yml`) to run both Pytest and Vitest suites.

## [1.0.0] - 2026-10-10
### Added
- Complete modular monolith architecture using FastAPI and React 19 / TypeScript / Vite.
- Append-only cryptographic ledger with sequential SHA-256 hash chaining and tamper detection.
- Deterministic CPU-based duplicate correlation engine using Haversine distance and Jaccard vocabulary scoring.
- Explainable Civic Priority Engine with transparent multi-factor breakdown.
- Strict State Machine guarding issue lifecycle transitions and preventing operator self-verification.
- Resolution verification gate supporting community dispute handling and independent citizen confirmation.
- Chronic Recurrence Hotspots intelligence for defects re-emerging at the same coordinates within 30 days.
- Portable ZIP evidence export package generator and standalone CLI verifier (`scripts/verify_evidence.py`).
- 5 realistic connected Indore demonstration scenarios idempotently seeded in `app.db.seed`.
- Workshop + Gridline + Studio Utility design system implemented with CSS variables.
- Full automated test suite (Pytest integration + E2E lifecycle workflow tests).
