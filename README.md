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

## 👥 Seeded Demonstration Accounts

The database comes pre-seeded with 5 interconnected scenarios set in **Indore Central & North Ward, Madhya Pradesh, India** (illustrative municipal data):

| Role | Email | Password | Access / Purpose |
| :--- | :--- | :--- | :--- |
| **Community Reviewer** | `reviewer@civictrace.local` | `ReviewerPass2026!` | Duplicate correlation desk & case consolidation |
| **Public Works Operator** | `lighting.operator@civictrace.local` | `OperatorPass2026!` | Logging repairs and submitting completion claims |
| **Citizen Observer** | `citizen.aarav@civictrace.local` | `CitizenPass2026!` | Reporting defects & submitting resolution verifications |
| **Administrator** | `admin@civictrace.local` | `AdminPass2026!` | System configuration & service area oversight |

*Note: The sign-in page features one-click demo credentials for quick inspection.*

---

## 🧪 Running Automated Tests

Run the full backend and end-to-end integration test suite:

```bash
cd services/api
python -m pytest app/tests/ -v
```

Tests include:
- Append-only SHA-256 hash chain verification
- Direct database row tamper detection
- Deterministic Haversine distance calculations
- Role-based conflict-of-interest guards (blocking operators from self-verifying)
- Full lifecycle E2E test (Submission → Verification → Repair Claim → Citizen Dispute → ZIP Export Tamper Check)

To verify an exported evidence package via CLI:
```bash
python scripts/verify_evidence.py storage/exports/<package_name>.zip
```

---

## 🎨 Visual Identity

CivicTrace follows the **Workshop + Gridline + Studio Utility** design philosophy:
- **Workshop:** Purposeful density, clear tools, and honest controls.
- **Gridline:** Ruled tables, baseline rhythm, and aligned data columns.
- **Studio Utility:** Restrained civic blue `#285E79`, verified green `#39735A`, attention orange `#BC7135`, and off-white `#F5F4F0` surfaces.

---

## 📜 License & Compliance

Licensed under the **Apache License, Version 2.0**. See [`LICENSE`](LICENSE) for details.
CivicTrace does not require or bundle proprietary Google Maps or Mapbox API keys.
