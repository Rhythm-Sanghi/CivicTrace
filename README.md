# CIVICTRACE

> **"A public record of problems worth fixing."**

CivicTrace is an open-source, evidence-oriented civic infrastructure investigation system. Unlike traditional complaint ticketing software where tickets disappear into an unverifiable "Resolved" status, CivicTrace provides an **append-only cryptographic event ledger**, **deterministic CPU-based duplicate correlation**, and **independent citizen verification**.

Built with a modular monolith architecture for **WarriorHacks 2.0** (Theme: Civic infrastructure accountability).

---

## 🏛️ The Core Difference

| Generic Complaint Portals | CivicTrace Evidence Ledger |
| :--- | :--- |
| **Disappearing Tickets:** Department marks "Closed" and ticket vanishes. | **Independent Verification Gate:** Repairs claimed by operators remain in `Awaiting Verification` until local citizens independently confirm resolution. |
| **Scattered Duplicates:** Multiple neighbors submit reports for the same pothole; each treated as isolated incidents. | **Deterministic Duplicate Engine:** Automatically correlates observations via Haversine proximity, vocabulary Jaccard similarity, and category weights into consolidated cases with preserved provenance. |
| **Opaque Status Changes:** Timestamps and notes can be edited or deleted by database administrators. | **Append-Only Cryptographic Ledger:** Every status change, assignment, work claim, and inspection is linked via SHA-256 hash chaining. Tampering is mathematically detectable. |
| **Memoryless Systems:** Repaired roads break down again 2 weeks later; previous history is erased. | **Chronic Recurrence Intelligence:** Tracks road and pipe failures re-emerging at the same coordinates within 30 days. |
| **Locked Data:** Data trapped inside proprietary municipal silos. | **Portable Evidence Package:** Exports ZIP evidence packages containing JSON timelines and SHA-256 integrity manifests. |

---

## ⚡ Quick Start (Local Development)

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
API Documentation will be live at: **`http://localhost:8000/docs`**

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

## 👥 Seeded Demonstration Accounts

The database comes pre-seeded with 5 interconnected scenarios set in **Indore Central & North Ward, Madhya Pradesh, India** (illustrative municipal data):

| Role | Email | Password | Access / Purpose |
| :--- | :--- | :--- | :--- |
| **Community Reviewer** | `reviewer@civictrace.local` | `ReviewerPass2026!` | Duplicate correlation desk, review overrides & case consolidation |
| **Public Works Operator** | `lighting.operator@civictrace.local` | `OperatorPass2026!` | Logging repairs and submitting completion claims |
| **Citizen Observer** | `citizen.aarav@civictrace.local` | `CitizenPass2026!` | Reporting defects & submitting resolution verifications |
| **Administrator** | `admin@civictrace.local` | `AdminPass2026!` | System configuration & service area oversight |

*Note: In development and local-demo modes, the sign-in page features one-click demo credentials. In production environments (`ENVIRONMENT=production`), demo account exposure is strictly disabled and missing secret keys cause safe startup termination.*

---

## 🧪 Running Automated Tests

### Backend Unit & Safeguard Suite (Pytest)
Run the full backend security and cryptographic ledger test suite:

```bash
cd services/api
python -m pytest app/tests/ -v
```

**16/16 tests pass**, covering:
1. Append-only SHA-256 hash chain verification and mathematical tamper detection
2. Deterministic Haversine spatial correlation and priority calculation
3. Conflict of interest enforcement: operators strictly blocked from self-verifying resolution claims (`403 Forbidden`)
4. Verification quorum and anti-sybil deduplication: requires 2 independent citizen confirmations to auto-resolve uncontested cases
5. Contradictory dispute protection: any citizen dispute (`STILL_UNRESOLVED`) immediately forces case state into `DISPUTED`
6. Claim cycle scoping: stale verification observations on prior disputed repair claims do not leak into new claim cycles after rework; citizens can re-verify new claims
7. Evidence authorization gating: unapproved or pending evidence cannot be downloaded publicly by anonymous callers or third-party citizens; approval required for public distribution
8. Unauthorized state transition prevention via centralized `CaseStateMachine`
9. Collision-resistant monotonic sequential public identifier allocators (`RPT-2026-XXXX`, `CAS-2026-XXXX`)
10. In-memory sliding-window IP rate limiting on authentication and reporting endpoints
11. Strict file magic bytes inspection (JPEG, PNG, WEBP, PDF) and 10MB streaming size validation
12. Full lifecycle end-to-end integration flow
13. ZIP export evidence manifest hashing and Zip-Slip traversal protection
14. Duplicate zip entry rejection preventing archive ambiguity attacks
15. Priority band engine mappings and critical hazard escalations
16. Health check probe and service status reporting

### Frontend Component Tests (Vitest)
```bash
cd apps/web
npm run test
```
**2/2 tests pass** (UI layout, numbered navigation, and Benchlight components).

### End-to-End Browser Automation & Screenshot Capture (Playwright)
```bash
python scripts/run_browser_e2e.py
```
Executes genuine headless browser workflows against the running application and captures full UI screenshots into `docs/screenshots/`.

To independently verify an exported evidence package via CLI:
```bash
python scripts/verify_evidence.py storage/exports/<package_name>.zip
```

---

## ⚙️ Architecture & Production Operational Notes

- **Rate Limiting Scope:** The built-in rate limiter utilizes an in-memory sliding window keyed by client IP. In single-process development and standard evaluation servers, it prevents basic spam and flooding with zero external dependencies. For distributed, multi-worker (e.g. Uvicorn clusters) or multi-container horizontal deployments, replace the in-memory store with a Redis / Valkey-backed sliding-window counter.
- **Cryptographic Ledger vs Digital Signatures:** CivicTrace provides tamper-evident append-only auditability via deterministic SHA-256 hash-chaining of canonical JSON payloads. This guarantees mathematical tamper detection and timeline ordering, but is distinct from PKI digital signatures.
- **Geographic Model:** CivicTrace uses an offline schematic map model with synthetic municipal defect data situated in Indore Ward 34. It does not connect to commercial mapping APIs or transmit user location externally.

---

## 🔀 Repository Default Branch Configuration

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

## 🎨 Visual Identity

CivicTrace follows the **Benchlight Design System** (Workshop + Gridline + Studio Utility):
- **Workshop:** Purposeful density, clear tools, and honest controls.
- **Gridline:** Ruled tables, baseline rhythm, aligned columns, and fine separators.
- **Studio Utility:** Light canvas `#f4f4f1`, warm brass accent `#795f2f`, soft beige selection `#e9e2d2`, and clean typography (`Segoe UI` + `Cascadia Mono`).

---

## 📜 License & Compliance

Licensed under the **Apache License, Version 2.0**. See [`LICENSE`](LICENSE) for details.
CivicTrace does not require or bundle proprietary Google Maps or Mapbox API keys. Demonstrations use an offline schematic map model of Indore Ward 34 with illustrative municipal records.
