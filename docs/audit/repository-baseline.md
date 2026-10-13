# CivicTrace Repository Audit & Architecture Baseline

**Audit Date:** October 11, 2026  
**Reference Base Commit:** `42ce27ed7158776d04f127f7da494d102cbb7f31`  
**Repository:** `https://github.com/Rhythm-Sanghi/CivicTrace`  
**Auditor:** Senior Software & Security Engineering Review  

---

## 1. Executive Summary

CivicTrace is an open-source civic accountability platform pairing public infrastructure problem reporting with verifiable lifecycle tracking, municipal audit trails, and duplicate detection.

The application has a functioning full-stack implementation:
- **Backend:** FastAPI, SQLAlchemy 2.0, SQLite (development/demo) / PostgreSQL/PostGIS (architecture target), Pydantic v2, JWT authentication, and SHA-256 state ledger hashing.
- **Frontend:** React 18, TypeScript, Vite, Tailwind CSS, Lucide icons, styled strictly in the *CivicTrace Workshop* (Workshop + Gridline + Studio Utility) design system.
- **Verification:** Vitest frontend unit tests, Pytest backend unit/integration tests, and 14-stage Playwright end-to-end browser workflows.

This audit establishes the baseline findings across reproducibility, security, concurrency, verification mechanics, and usability before systematic hardening.

---

## 2. Inventory & File Tracking Baseline

### 2.1 Git Working Tree & Root Ignored Pattern Incident
- **Root `.gitignore` Flaw:** Prior to this audit, `.gitignore` contained an unanchored rule:
  ```gitignore
  lib/
  ```
  Intended to ignore local Python virtual environment folders (e.g. Unix `/lib`), this unanchored rule unintentionally caused Git to silently ignore `apps/web/src/lib/api.ts`.
- **Remediation:** Root `.gitignore` was anchored to `/lib/` and `/lib64/`. As a result, `apps/web/src/lib/api.ts` was properly recognized by Git and verified intact on disk.

### 2.2 Dependency Manifest Inventory
- **Backend (`services/api/`):**
  - Previously lacked explicit manifest files, relying on ad-hoc environment installation.
  - Added `requirements.txt` with strict pinned version bounds (`fastapi>=0.110.0,<0.116.0`, `uvicorn>=0.28.0,<0.31.0`, `sqlalchemy>=2.0.28,<2.1.0`, `alembic>=1.13.1`, `pydantic>=2.6.4`, `python-jose>=3.3.0`, `passlib>=1.7.4`, `bcrypt>=4.0.0`, `python-multipart>=0.0.9`, `shapely>=2.0.3`, `geoalchemy2>=0.14.4`, `pytest>=8.1.0`, `httpx>=0.27.0`, `ruff>=0.3.0`).
  - Added standard `pyproject.toml` with project metadata and tool configurations for `pytest` and `ruff`.
- **Frontend (`apps/web/`):**
  - Managed via `package.json` with lockfile `package-lock.json`.
  - Supports clean deterministic installation via `npm ci`.

---

## 3. Security, Authorization & Privacy Baseline

| Scope | Current Status | Vulnerability / Deficiency | Hardening Plan |
| :--- | :--- | :--- | :--- |
| **Report Moderation** | Reports automatically default to `APPROVED` and spawn public `Case` records. | Unmoderated submissions (including spam or harmful text) immediately become publicly queryable cases. | Untrusted / anonymous reports default to `PENDING`. Add explicit moderation endpoint (`POST /reports/{id}/moderate`). Only `APPROVED` reports surface publicly. |
| **Evidence Upload Access Control** | `upload_report_evidence` accepts optional credentials without checking ownership. | Any user can attach arbitrary files to any report ID. | Enforce authentication; ensure current user is the report author or an authorized reviewer/admin. |
| **Evidence File Safety** | MIME type accepted directly from client header; unbounded read. | Potential malicious file uploads, MIME spoofing, memory exhaustion. | Validate magic bytes (JPEG, PNG, WEBP, PDF), enforce strict file size cap (10MB), sanitize stored filenames. |
| **Evidence Download Access** | `download_evidence_asset` streams file based solely on asset ID. | Unauthenticated exfiltration of unapproved/private case attachments. | Enforce authorization: asset must belong to an approved public report or caller must be author/staff. |
| **Rate Limiting** | Missing on submission & auth routes. | Potential denial-of-service or brute-force credential stuffing. | Add in-memory sliding window rate limiting for `/auth/login` and `/reports`. |
| **Privacy Redaction** | Private citizen contact information in database models. | Risk of accidental public exposure in APIs and zip export bundles. | Enforce strict schema allowlists preventing citizen email/phone exposure in public responses and export manifests. |

---

## 4. Concurrency, State Machine & Ledger Integrity Baseline

### 4.1 Public Identifier Allocation Defect
- **Defect:** `reports.py` and `cases.py` currently generate human IDs using:
  ```python
  count = db.query(Report).count() + 1
  # or
  count = db.query(Case).count() + 1
  ```
- **Consequence:** Vulnerable to race conditions under concurrent submissions and ID collisions if older records are purged or filtered.
- **Hardening Plan:** Introduce atomic collision-resistant sequential identifier generator (e.g. date-prefixed monotonic sequence or sequence table with transactional locking and fallback collision check).

### 4.2 State Machine Enforcement & Transaction Atomicity
- **Defect:** Some endpoints (`submit_resolution_claim`, `assign_case_department`, `submit_verification_observation`) update `case.state` directly without delegating to `CaseStateMachine`.
- **Consequence:** Potential bypass of transition guards, inconsistent timeline entries, and ledger hash desynchronization.
- **Hardening Plan:** Unify all case state transitions through a transactional domain method. Each transition must validate permissions, update state, compute SHA-256 ledger event pre-images, and commit atomically.

### 4.3 Ledger Pre-image Format
- **Current State:** Hash computation concatenates case ID, action, state, and previous hash.
- **Hardening Plan:** Standardize cryptographic pre-image with canonical JSON serialization, explicit ISO-8601 UTC timestamp, actor metadata hash, and schema version to prevent pre-image ambiguity.

### 4.4 Data Claims & Geographic Authenticity
- Indore Ward 34 data in demo seeds is schematic and illustrative. Public documentation must state clearly that demo coordinates and municipal boundaries are realistic civic test fixtures rather than certified live government feeds.

---

## 5. Phased Remediation Schedule

- **Phase A (Completed):** Root `.gitignore` repair, `apps/web/src/lib/api.ts` tracking restoration, backend dependency declarations (`requirements.txt`, `pyproject.toml`), baseline audit report.
- **Phase B (Next):** Security, Privacy & Authorization Matrix hardening (moderation lifecycle, upload magic bytes validation, asset access control, rate limiting).
- **Phase C:** Concurrency, state machine centralization, collision-free identifiers, export allowlist sanitization, and SHA-256 ledger verification.
- **Phase D:** Frontend contract alignment, plain human-centered civic terminology overhaul, and CivicTrace Workshop UI polish.
- **Phase E:** Backend and frontend test coverage expansion, Playwright E2E verification, CI workflow modernization.
- **Phase F:** Comprehensive README overhaul, clean setup scripts, removal of dead code/stale documentation.
