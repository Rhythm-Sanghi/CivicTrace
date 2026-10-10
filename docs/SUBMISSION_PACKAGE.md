# CivicTrace — WarriorHacks 2.0 Submission Package

## 1. Project Title & Tagline
- **Project Title:** CivicTrace
- **One-Line Elevator Pitch:** An evidence-oriented public issue investigation system that ensures public infrastructure complaints do not disappear simply because an operator marks them "resolved."
- **Category / Theme:** Civic Technology & Public Infrastructure Accountability

---

## 2. Devpost Submission Narrative

### Inspiration
In almost every city, reporting a pothole, a snapped live wire, or a municipal water leak feels like shouting into a void. A citizen submits a complaint on a generic municipal portal, receives a generic ticket ID, and two weeks later receives an automated SMS declaring the issue "Resolved." 

When they walk out the door, the pothole is still there, or worse, poorly patched with sand that washed away during the first rainstorm. 

CivicTrace was created on a single non-negotiable premise: **A complaint should not disappear simply because someone changes its status to resolved.** Public infrastructure requires evidence, community corroboration, independent verification, and cryptographic permanence.

---

### What CivicTrace Does
CivicTrace is not another generic ticket management portal. It is an **evidence-oriented civic investigation system**:

1. **Intake & Evidentiary Standards:** Citizens submit defect reports with precise WGS84 coordinates, photographic evidence, and descriptions through a structured four-stage workflow (Describe &rarr; Locate &rarr; Evidence &rarr; Review) with automatic local draft preservation.
2. **Deterministic Duplicate Correlation:** When multiple neighbors report the same crater or burst pipe, CivicTrace's deterministic correlation engine matches them using Haversine distance (&le; 50m), tokenized vocabulary similarity, and category weights. Duplicate reports are consolidated into a shared case dossier, preserving every citizen's observation provenance.
3. **Explainable Civic Priority Scoring:** Transparent, deterministic scoring (1.0 to 10.0 scale) driven by intrinsic hazard severity (e.g., exposed high-voltage cables score higher base weights than cosmetic issues), independent corroboration bonuses (+0.4 per extra observer), unresolved duration bonuses, and chronic recurrence flags.
4. **Append-Only Cryptographic Event Ledger:** Every lifecycle event (creation, duplicate link, assignment, operator claim, dispute, verification) is recorded as a sequential event with an immutable SHA-256 hash chained to the preceding event. Any back-door alteration to the database breaks the mathematical chain and is flagged immediately.
5. **Resolution Verification Gate & Dispute Safeguard:** An operator claiming a repair (`RESOLUTION_CLAIMED`) does not close the case; it moves to `AWAITING_VERIFICATION`. Only qualifying independent citizen observations (`CONFIRMED_FIXED`) or reviewer consensus can close a case (`RESOLVED`). Crucially, if an observer files a dispute (`STILL_UNRESOLVED`), the case instantly transitions to `DISPUTED`, triggering review and ordering department rework.
6. **Portable Evidence Export & Tamper Verification:** Anyone can download a standalone `.zip` evidence package containing canonical JSON event timelines, observation logs, and a `manifest.json` with individual SHA-256 digests. If any byte in the exported case history is tampered with, the included offline CLI verification tool mathematically identifies the altered file.
7. **Benchlight-Class Visual Identity:** Rebuilt with strict visual parity to the Benchlight desktop productivity software—featuring numbered navigation (`01 Overview`, `02 Cases`, `03 Intelligence`), warm brass `#795f2f` accents, flat measurement bars, sortable tables with 2-line title clamping, and an interactive schematic map canvas.

---

### How We Built It (Technologies Used)
- **Backend & Core Engine:** Python 3.11, FastAPI, SQLAlchemy 2.0, Alembic, SQLite (modular monolith architecture, PostgreSQL/PostGIS portable).
- **Security & Integrity:** Cryptographic SHA-256 hash chaining, canonical JSON serialization, JWT authentication, Passlib/Bcrypt, role-based access control (Citizen, Reviewer, Operator, Administrator).
- **Algorithms:** Deterministic spatial Haversine distance, tokenized Jaccard similarity, explainable multi-component priority scoring.
- **Frontend & Design System:** React 19, TypeScript, Vite, custom Benchlight design tokens (canvas `#f4f4f1`, surface `#fafaf8`, accent `#795f2f`, Cascadia Mono typography).
- **Validation & Quality Assurance:** Pytest (10/10 passing tests), Vitest (2/2 passing tests), Playwright real-browser interactive E2E automation (all 14 lifecycle stages verified).

---

### Challenges We Encountered
1. **Preventing Conflicts of Interest in Resolution:** Building a verification system that cannot be gamed required strict backend safeguards: department operators are strictly blocked (`403 Forbidden`) from self-verifying their own resolution claims. Uncontested closures require a quorum of two independent citizen observations.
2. **Deterministic Correlation Without Heavy Cloud AI:** We wanted CivicTrace to run completely offline on a low-spec laptop without requiring expensive cloud AI API keys. We designed a pure-CPU mathematical engine combining spatial radius clamping with tokenized Jaccard text scoring that consistently matches nearby reports in sub-millisecond time.
3. **Benchlight Visual Parity:** Translating dense municipal data into Benchlight's calm, utilitarian desktop aesthetic required careful typographic hierarchy, flat `<dl>` measurement strips with vertical dividers, stable table column allocations, and decluttered map markers.

---

### Accomplishments We're Proud Of
- **100% Verified Real Browser E2E:** Unlike submissions that rely on mocked data, our 14-step automated Playwright suite runs against the real database, signs in through the UI, files complaints, merges duplicates, logs claims, disputes resolutions, exports ZIP packages, and successfully catches intentional byte-level tampering.
- **Explainable Priority & Mathematical Tamper Detection:** No "black box" machine learning—every priority score explains its exact components, and every exported record can be mathematically audited with standard command-line tools.
- **High Information Density & Ergonomics:** Fast keyboard-navigable tables, collapsible inspectors, responsive mobile adaptation, and clean visual feedback.

---

### What We Learned
- Public trust in civic technology does not come from glossy marketing dashboards; it comes from **verifiable guarantees**. Knowing that a ticket cannot be silently closed by an administrator without leaving an audit trail fundamentally changes the relationship between citizens and public agencies.

---

### Future Roadmap
- Native PostGIS geospatial indexing for multi-city scale.
- Cryptographic ed25519 digital signature signing for municipal inspectors with public key registries.
- Offline-first Service Worker with background sync for field inspectors in low-connectivity areas.
- Automated SMS/WhatsApp notifications for citizens whose reports are merged into active case dossiers.

---

## 3. Curated Screenshots & Captions (Devpost Selection)

1. **`01_overview.png` — Overview & Indore Ward 34 Schematic Investigation Canvas**  
   *Caption: Compact Benchlight-style overview featuring real-time civic telemetry, flat measurement strips, and an offline schematic grid canvas plotting active municipal infrastructure defects with interactive pan/zoom controls.*

2. **`02_cases_explorer.png` — Public Infrastructure Cases Explorer**  
   *Caption: High-density flat data table with stable column widths, 2-line title clamping, interactive column sorting, and responsive multi-field filtering across categories and priority bands.*

3. **`03_selected_case_inspector.png` — Collapsible Case Inspector Pane**  
   *Caption: Contextual case inspector providing complete defect summaries, WGS84 coordinates, civic priority breakdowns, and quick navigation into complete case dossiers without losing table context.*

4. **`06_duplicate_suggestion.png` — Reviewer Duplicate Correlation & Consolidation Desk**  
   *Caption: Community reviewer workspace displaying deterministic correlation calculations (73.1% composite match, 15.1m distance) for merging corroborating citizen observations into unified investigation dossiers.*

5. **`07_resolution_dispute.png` — Community Dispute & Verification Safeguard Station**  
   *Caption: A disputed case (CAS-2026-0002) where a citizen observation rejected an operator's claimed repair, immediately transitioning the case to DISPUTED and enabling authorized reviewer mediation.*

6. **`08_evidence_timeline.png` — Append-Only Cryptographic Accountability Ledger**  
   *Caption: Immutable case timeline where every action is sequentially chained using SHA-256 cryptographic hashes. Tampering with any historical event is mathematically detected.*

7. **`09_intelligence.png` — Neighborhood Intelligence & Telemetry**  
   *Caption: Verifiable municipal telemetry showing defect category shares, lifecycle state distributions, case age brackets, resolution claim verification audits, and chronic recurrence hotspots.*

8. **`10_report_issue_form.png` — Structured 4-Stage Defect Intake Form**  
   *Caption: Citizen reporting workflow featuring live input validation, browser GPS acquisition, photo evidence preview with 10MB limits, and pre-submission review summaries.*

---

## 4. Timed 2–3 Minute Video Demonstration Script

- **Total Duration:** 2 minutes 45 seconds
- **Speaker:** Lead Developer / Presenter

### [0:00 – 0:30] Introduction & The Problem
> *"Hello, this is CivicTrace. In almost every municipal portal today, citizen complaints go into a black box. A worker marks a ticket as resolved, the complaint disappears, and the pothole or broken pipe is still there.*
> *CivicTrace is built on one simple rule: a complaint should never disappear just because someone changes its status. It is an evidence-oriented public issue investigation system built with Benchlight's calm, utilitarian design language."*

### [0:30 – 1:00] Overview & Public Explorer
> *(Screen shows `http://localhost:5173/` and navigation to `02 / Cases`)*
> *"Here on the Overview, we see real-time neighborhood telemetry for our demonstration area in Indore Ward 34. Our schematic map canvas lets us inspect active defects with pan, zoom, and decluttered markers.*
> *In the Cases Explorer, our table maintains high density with stable column widths and two-line clamped titles. We can click any case or hit space to open the inspector, sort by reference or priority, or collapse the inspector to expand our view."*

### [1:00 – 1:35] Citizen Intake & Deterministic Correlation
> *(Screen navigates to `04 / Report issue` and then `05 / Reviewer desk`)*
> *"When a citizen reports a hazard—like this exposed conduit on Chhatri Bagh Road—our structured 4-stage intake provides live validation, GPS coordinate capture, photographic evidence preview, and draft persistence.*
> *When a second citizen reports the same hazard nearby, CivicTrace doesn’t create two disconnected tickets. Our deterministic engine computes spatial distance and vocabulary similarity—here calculating a 73% composite match 15 meters away—and allows our community reviewer to consolidate them into a shared dossier."*

### [1:35 – 2:15] The Resolution Verification Gate & Dispute Safeguard
> *(Screen shows `CAS-2026-0007` transitioning from claim to dispute)*
> *"Now, the critical difference: an operator claiming a repair does not close the case. It enters 'Awaiting Verification'. Operators are strictly forbidden by backend policy from verifying their own work.*
> *When citizen Aarav inspects the site and finds unbolted wiring, he submits a dispute observation. The case instantly moves into DISPUTED status. The community reviewer can inspect the dispute and order department rework, returning the case to In Progress."*

### [2:15 – 2:45] Cryptographic Ledger & Tamper Detection
> *(Screen shows the timeline with SHA-256 hashes and terminal ZIP export verification)*
> *"Every single action—from report creation to dispute—is recorded in an append-only ledger chained with SHA-256 hashes. Anyone can download a complete ZIP evidence package.*
> *If anyone tampers with a single byte in that export, our verification tool immediately detects the hash mismatch and flags the exact corrupted file. CivicTrace provides a permanent, verifiable public record of problems worth fixing. Thank you."*

---

## 5. Demonstration Recording Checklist

- [ ] Ensure backend is running (`uvicorn app.main:app --port 8000`)
- [ ] Ensure frontend is running (`npm run dev -- --port 5173`)
- [ ] Reset to fresh demonstration database (`python -m app.db.seed` in `services/api`)
- [ ] Browser window set to 1440x900 or 1920x1080 resolution at 100% zoom
- [ ] Pre-open tabs:
  1. `http://localhost:5173/` (Overview)
  2. `http://localhost:5173/explorer` (Cases Explorer)
  3. `http://localhost:5173/report` (Report Issue)
  4. `http://localhost:5173/reviewer` (Reviewer Desk, signed in as `reviewer@civictrace.local`)
  5. `http://localhost:5173/neighborhood` (Intelligence)
- [ ] Terminal window open to run `python scripts/verify_evidence.py` to show mathematical tamper detection

---

## 6. Exact Remaining Manual Actions for Developer

1. **Record Video Demonstration:** Follow the 2:45 video script above using OBS or Loom and upload to YouTube (unlisted) or Vimeo.
2. **Submit on Devpost:** Copy the Narrative, Technologies, and Screenshot Captions into the Devpost WarriorHacks 2.0 submission form.
3. **Attach GitHub Repository URL:** Ensure the repository visibility is set appropriately for hackathon judges.
