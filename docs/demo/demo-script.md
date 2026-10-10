# CivicTrace Hackathon Demonstration Script (2–3 Minutes)

**Target Competition:** WarriorHacks 2.0  
**Theme:** Solve an issue affecting a community, county, state, or nation  
**Demo Geography:** Indore Central & North Ward, Madhya Pradesh, India (Simulated realistic local infrastructure data)

---

### [0:00 – 0:20] The Public Problem: The Vanishing Complaint
- **Voiceover:** *"In cities across the world, citizen complaint portals suffer from a fatal flaw: complaints disappear as soon as an agency clicks 'Mark Resolved'. Citizens have no way to verify whether the pothole was actually paved, whether the streetlights were actually turned back on, or whether the patch washed away two weeks later."*
- **Visual:** Open CivicTrace Home View (`http://localhost:5173/`).
- **Key Callout:** The guiding principle banner: *"A complaint should not disappear simply because someone changes its status to resolved."*

---

### [0:20 – 0:45] Submitting an Infrastructure Observation
- **Action:** Click **"Report Issue"** in the top navigation.
- **Workflow:** Select *Potholes and Damaged Roads*, enter a title on MG Road, show GPS coordinates for Indore Ward 34, provide a privacy-preserving citizen pseudonym (*Aarav Mehta*), and submit.
- **Key Feature:** Automatic public ID generation (`RPT-2026-XXXX`) and immediate promotion into cryptographic evidence tracking.

---

### [0:45 – 1:10] Deterministic Duplicate Correlation & Consolidation
- **Visual:** Navigate to **"Reviewer Workspace"** (Signed in as `reviewer@civictrace.local`).
- **Action:** Show candidate reports submitted by multiple citizens near Rajwada Palace.
- **Explanation:** Explain the 100% CPU-based deterministic duplicate engine (Haversine distance within 300m, vocabulary Jaccard similarity, category match, and temporal decay). Show the exact mathematical explanation bullets.
- **Action:** Click **"Consolidate into Case"**—the reports merge into `CAS-2026-0001` with full observation provenance preserved.

---

### [1:10 – 1:40] Resolution Claims vs. The Dispute Gate
- **Visual:** Switch to **"Operator Workspace"** (Public Works Operator `lighting.operator@civictrace.local`).
- **Action:** Inspect `CAS-2026-0002` (56 Dukan Streetlight failure).
- **Workflow:** The operator logs repairs (*"Replaced 3 LED drivers"*). The case moves to **Awaiting Verification**—not closed.
- **The Dispute:** Switch to citizen view. Citizen inspects at night, finds pole #15 dark, and files a `STILL_UNRESOLVED` observation. The case moves to **DISPUTED**.
- **Key Differentiator:** Operators cannot self-verify or silence conflicting citizen evidence.

---

### [1:40 – 2:05] Verified Resolution & Chronic Recurrence Hotspots
- **Visual:** Open `CAS-2026-0003` (Palasia Square water pipe repair) and show an independent citizen's verified confirmation (*"Water pipe dry, new asphalt solid"*).
- **Visual:** Open **"Intelligence & Metrics"** tab.
- **Key Feature:** Highlight **Chronic Recurrence Hotspots** (`CAS-2026-0005` at Sarafa Bazar Gate). Explain how CivicTrace correlates recurring failures when a repair collapses within 30 days of closure.

---

### [2:05 – 2:30] Cryptographic Hash Chaining & Evidence Export
- **Visual:** Open the Case Details Dossier. Show the append-only SHA-256 event timeline.
- **Demonstration:** Point out the live cryptographic ledger verification badge (*"All events verify in strict sequential SHA-256 hash chaining"*).
- **Action:** Click **"Export Cryptographic Evidence Package (ZIP)"**.
- **CLI Verification:** Run `python scripts/verify_evidence.py export.zip` to demonstrate mathematical tamper detection.

---

### [2:30 – 2:45] Impact, Feasibility, & Scalable Sustainability
- **Voiceover:** *"CivicTrace is built on a clean modular monolith architecture with zero mandatory cloud AI dependencies or proprietary map subscriptions. It gives communities a permanent, verifiable public record of problems worth fixing."*
