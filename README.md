# CIVICTRACE

> **"A public record of problems worth fixing."**

CivicTrace is an open-source, evidence-oriented civic infrastructure investigation system. Unlike traditional complaint ticketing software where tickets disappear into an unverifiable "Resolved" status, CivicTrace provides an **append-only cryptographic event ledger**, **deterministic CPU-based duplicate correlation**, and **independent citizen verification**.

Built with a modular monolith architecture for **WarriorHacks 2.0** (Theme: Civic infrastructure accountability).

---

## The Core Difference

| Generic Complaint Portals | CivicTrace Evidence Ledger |
| :--- | :--- |
| **Disappearing Tickets:** Department marks "Closed" and ticket vanishes. | **Citizen Verification Gate:** Operator-claimed repairs remain in `Awaiting Verification` pending citizen observation. Under conservative verification policy, auto-closure requires trusted identity credentials; otherwise authorized reviewer sign-off is required. |
| **Scattered Duplicates:** Multiple neighbors submit reports for the same pothole; each treated as isolated incidents. | **Deterministic Duplicate Engine:** Automatically correlates observations via Haversine proximity, vocabulary Jaccard similarity, and category weights into consolidated cases with preserved provenance. |
| **Opaque Status Changes:** Timestamps and notes can be edited or deleted by database administrators. | **Tamper-Evident Cryptographic Ledger:** Every status change, assignment, work claim, and inspection is linked via SHA-256 hash chaining. Event modifications are mathematically detectable, and external Ed25519 checkpoints protect against full database rewrites. |
| **Memoryless Systems:** Repaired roads break down again 2 weeks later; previous history is erased. | **Chronic Recurrence Intelligence:** Tracks road and pipe failures re-emerging at the same coordinates (50-meter radius) within 60 days. |
| **Locked Data:** Data trapped inside proprietary municipal silos. | **Portable Evidence Package:** Exports ZIP evidence packages containing JSON timelines and SHA-256 integrity manifests. |

---

## Quick Start (Local Development)

CivicTrace requires zero paid APIs, zero cloud AI subscriptions, and no mandatory Docker. It runs smoothly on any modern laptop (e.g. Windows 11 / WSL2 / macOS / Linux).

### Prerequisites
- **Python 3.11+**
- **Node.js 18+ & npm**

### 1. Backend Setup

```bash
# From repository root:
# 1. Activate virtual environment (or create with python -m venv .venv)
.\.venv\Scripts\activate   # (On Linux/macOS: source .venv/bin/activate)

# 2. Install dependencies
pip install -r services/api/requirements.txt  # or pip install fastapi uvicorn sqlalchemy alembic pydantic bcrypt pyjwt httpx pytest

# 3. Initialize environment file
cp .env.example .env

# 4. Seed the database with realistic demonstration scenarios
cd services/api
python -m app.db.seed

# 5. Start the FastAPI backend server
uvicorn app.main:app --reload --port 8000
```
API Documentation will be live at: **`http://localhost:8000/api/v1/docs`** (ReDoc: **`http://localhost:8000/api/v1/redoc`**)

---

### 2. Frontend Setup

```bash
# In a new terminal, navigate to apps/web:
cd apps/web

# 1. Install dependencies
npm install

# 2. Run the Vite development server
npm run dev
```
CivicTrace Web Interface will be live at: **`http://localhost:5173`**

---

### 3. Database Migrations & Schema Management

CivicTrace uses Alembic for declarative schema versioning and database portability:

```bash
cd services/api
alembic upgrade head
```

- **Local Demo / Development Mode:** Zero-setup table bootstrapping is supported via `AUTO_CREATE_TABLES=True`.
- **Production Mode:** Alembic migrations (`alembic upgrade head`) are the authoritative schema mechanism. The production startup gate enforces `AUTO_CREATE_TABLES=False`.

---

## Seeded Demonstration Accounts

The database comes pre-seeded with 5 interconnected scenarios set in **Indore Central & North Ward, Madhya Pradesh, India** (illustrative municipal data):

| Role | Email | Password | Access / Purpose |
| :--- | :--- | :--- | :--- |
| **Community Reviewer** | `reviewer@civictrace.local` | `ReviewerPass2026!` | Duplicate correlation desk, review overrides & case consolidation |
| **Public Works Operator** | `lighting.operator@civictrace.local` | `OperatorPass2026!` | Logging repairs and submitting completion claims |
| **Citizen Observer** | `citizen.aarav@civictrace.local` | `CitizenPass2026!` | Reporting defects & submitting resolution verifications |
| **Administrator** | `admin@civictrace.local` | `AdminPass2026!` | System configuration & service area oversight |

*Note: In development and local-demo modes, the sign-in page features one-click demo credentials. In production environments (`ENVIRONMENT=production`), demo account exposure is strictly disabled and missing secret keys cause safe startup termination.*

---

## Running Automated Tests

### Backend Automated Test Suite (Pytest)
Run the full backend security, multiprocess concurrency, ledger authenticity attack, and workflow race test suite:

```bash
cd services/api
pytest app/tests/ -v
```

**75/75 tests pass**, covering:
1. Append-only SHA-256 hash chain verification and mathematical tamper detection
2. Deterministic Haversine spatial correlation and priority calculation
3. Conflict of interest enforcement: operators strictly blocked from self-verifying resolution claims (`403 Forbidden`)
4. Verification quorum and anti-sybil guard: conservative policy (`REQUIRE_TRUSTED_IDENTITY_FOR_AUTO_RESOLVE=True`) prevents ordinary accounts from auto-closing cases without reviewer sign-off; administrator identity enrollment required for verified citizen auto-resolution
5. Contradictory dispute protection: any citizen dispute (`STILL_UNRESOLVED`) immediately forces case state into `DISPUTED`
6. Claim cycle scoping: stale verification observations on prior disputed repair claims do not leak into new claim cycles after rework; citizens can re-verify new claims
7. Evidence authorization gating: unapproved or pending evidence cannot be downloaded publicly by anonymous callers or third-party citizens; approval required for public distribution
8. Path traversal confinement preventing filesystem escape outside upload storage directory
9. Unauthorized state transition prevention via centralized `CaseStateMachine`
10. Database-enforced atomic sequence allocators (`RPT-2026-XXXX`, `CAS-2026-XXXX`, per-case event index) via dedicated `sequence_counters` table
11. Multiprocess concurrency: 4 concurrent OS worker processes allocating IDs with zero collisions, zero gaps, and durability across rollbacks
12. Comprehensive workflow concurrency races (8 distinct multi-session scenarios):
    - Concurrent duplicate candidate approval
    - Concurrent candidate approval vs rejection race
    - Case assignment vs operator transition race
    - Multiple concurrent resolution claims (enforced by partial unique DB index `uq_active_resolution_claim_per_case`)
    - Concurrent positive observation vs dispute observation
    - Simultaneous automatic-closure attempts
    - Evidence upload vs report moderation rejection
    - Concurrent event ledger appends
13. Complete ledger authenticity attacks (13 vectors tested across `FILE_INTEGRITY` and `TRUSTED_AUTHENTICITY` modes):
    - Payload event modification
    - Actor metadata modification
    - Event reordering
    - Intermediate event deletion
    - Final event deletion
    - Multiple final events truncation
    - Complete forged hash chain recalculation
    - Signer key replacement attack
    - Stale valid export replay
    - Direct database tampering of actor identity
    - Direct database tampering of event timestamp
    - Direct database tampering of public actor label
    - Historical schema version 1 backward compatibility preservation
14. Atomic backup & recovery security (4 comprehensive operational scenarios):
    - Strict exclusion of private signing keys and credentials from application archives
    - Point-in-time consistency during concurrent upload races, temporary fragments (.tmp, .part), and uncommitted files
    - Discrimination between accidental disk/transfer corruption (SHA-256) and malicious archive replacement (Ed25519 signature)
    - Controlled, encrypted key backup lifecycle using PBKDF2-HMAC-SHA256 and AES-256-GCM
15. In-memory sliding-window IP rate limiting with thread safety, prune intervals, and deterministic test clock
16. Reverse proxy header trust guard: `X-Forwarded-For` ignored unless `BEHIND_PROXY` is enabled and request originates from a trusted peer
17. Strict file magic bytes inspection (JPEG, PNG, WEBP, PDF) and 10MB streaming size validation
18. Full lifecycle end-to-end integration flow
19. Fail-closed ZIP export package verification (`FILE_INTEGRITY` vs `TRUSTED_AUTHENTICITY`) with Ed25519 signature checks
20. Guest upload capability tokens: cryptographically secure token generation, SHA-256 database hashing, constant-time verification, 120-min expiry, and automatic revocation on moderation rejection
21. Database-backed session revocation (`revoked_tokens` table) with cross-process consistency and token expiry cleanup
22. Reviewer pending report moderation queue and production moderation defaults (`REQUIRE_REPORT_MODERATION=True`)
23. Statistical median computation for even-length distributions
24. Hard bcrypt 72-byte password length validation preventing silent password truncation
25. Constant-time dummy password hashing on authentication failures preventing account enumeration timing attacks
26. HttpOnly cookie session support with explicit `/auth/logout` revocation
27. Health check probe and service status reporting
28. Fail-safe disposable test database configuration guard preventing execution against development or production databases
29. Genuine PostgreSQL/PostGIS integration coverage: role boundaries, case lifecycle, duplicate adjudication, resolution claim unique constraints, cross-session token revocation, concurrent ledger writes, and schema migration correctness from empty to populated schemas

### Frontend Component Tests (Vitest)
```bash
cd apps/web
npm run test
```
**7/7 tests pass**, covering:
- Layout and navigation components
- CivicTrace Workshop and gridline design tokens
- Local storage token isolation
- Authentication error handling
- Reviewer moderation workspace interactions
- Case state transitions and dispatch controls
- Upload boundary restrictions and dispute handling

### End-to-End Browser Automation & Verification (Playwright)
```bash
python scripts/run_browser_e2e.py
```
Executes genuine headless Chromium browser workflows covering the entire 14-step civic lifecycle on a disposable database:
- Citizen registration & login
- Report submission & evidence upload
- Pending moderation boundary containment
- Reviewer moderation approval via UI
- Department dispatch & operator claim submission via UI
- Citizen dispute observation & closure blocking via UI
- Reviewer adjudication & rework ordering via UI
- Subsequent resolution confirmation
- Signed evidence export & offline verification
- Session logout & token replay rejection
- Department boundary isolation (unauthorized operator blocked HTTP 403)
- Evidence package tamper rejection
- Accessibility verification: 320px mobile viewport, keyboard focus traversal, and 200% zoom rendering

---

## 🛠️ Operational & Release Tooling

### Backup, Restore & Key Rotation Utility (`scripts/backup_restore.py`)
CivicTrace includes a unified operational management tool for coordinated database and evidence storage backups:

```bash
# 1. Atomic coordinated backup of database and uploaded evidence
python scripts/backup_restore.py backup --db-path services/api/civictrace_dev.db --uploads-dir services/api/storage/uploads --out-dir backups/

# 2. Integrity-verified restore to a target location
python scripts/backup_restore.py restore --archive backups/civictrace_backup_20261013_104500.zip --db-target restored/civictrace_dev.db --uploads-target restored/uploads/

# 3. Clean up unreferenced or orphaned uploaded evidence files
python scripts/backup_restore.py cleanup-uploads --db-path services/api/civictrace_dev.db --uploads-dir services/api/storage/uploads/

# 4. Generate or rotate Ed25519 evidence signing keys with automatic timestamped backup
python scripts/backup_restore.py rotate-key --keys-dir services/api/storage/keys/
```

---
## Release Readiness Assessment

| Deployment Tier | Status | Rationale |
| :--- | :--- | :--- |
| **Local Demo** | **READY** | Zero configuration required; SQLite atomic sequences, 63/63 automated backend tests, 7/7 frontend tests, 14-step user-driven browser verification, and offline mock map work out of the box. |
| **Hackathon Demo** | **READY** | Fully functional evidence lifecycle, append-only cryptographic ledger, tamper detection, reviewer moderation desk, and responsive CivicTrace Workshop UI. |
| **Private Pilot** | **CONDITIONALLY READY** | Requires deployment with PostgreSQL 16 / PostGIS container, production environment variables (`ENVIRONMENT=production`), dedicated external keypair storage, and reverse proxy with TLS termination. |
| **Public Production** | **NOT READY** | Requires distributed rate limiting (e.g. Redis/Valkey), official municipal single sign-on / national ID integration (Aadhaar / DigiLocker / eID), anti-DDoS / WAF protection, and virus/malware scanner integration on binary uploads. |

---

## Repository Default Branch Configuration

The remote repository default branch is currently set to `master`. To align with standard modern conventions and make `main` the authoritative default branch on GitHub:

1. **Via GitHub Web UI:**
   - Navigate to the repository on GitHub: `https://github.com/Rhythm-Sanghi/CivicTrace`
   - Go to **Settings** > **General** > **Default branch**
   - Click the switch icon (⇄) next to `master`
   - Select `main` from the dropdown list and click **Update**
   - Confirm the prompt to switch the default branch to `main`.
2. **Via GitHub CLI (`gh`):**
   ```bash
   gh repo edit Rhythm-Sanghi/CivicTrace --default-branch main
   ```
*(Do not delete the `master` branch until confirmed and approved).*

---

## Visual Identity

CivicTrace follows the **CivicTrace Workshop Design System** (Workshop + Gridline + Studio Utility):
- **Workshop:** Purposeful density, clear tools, and honest controls.
- **Gridline:** Ruled tables, baseline rhythm, aligned columns, and fine separators.
- **Studio Utility:** Light canvas `#f4f4f1`, warm brass accent `#795f2f`, soft beige selection `#e9e2d2`, and clean typography (`Segoe UI` + `Cascadia Mono`).

---

## License & Compliance

Licensed under the **Apache License, Version 2.0**. See [`LICENSE`](LICENSE) for details.
CivicTrace does not require or bundle proprietary Google Maps or Mapbox API keys. Demonstrations use an offline schematic map model of Indore Ward 34 with illustrative municipal records.
