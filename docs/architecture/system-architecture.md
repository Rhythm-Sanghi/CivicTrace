# CivicTrace — Architectural Decision Records & Security Architecture

## 1. System Overview & Principles

CivicTrace is designed as a **Modular Monolith** prioritizing maintainability, data integrity, and local developer ergonomics.

```
                              ┌───────────────────────────────────┐
                              │    Citizen / Reviewer / Operator  │
                              └─────────────────┬─────────────────┘
                                                │
                                    HTTP / REST │ JSON
                                                ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          FastAPI Application Gateway                        │
│                                                                             │
│  ┌───────────────────────┐  ┌───────────────────────┐  ┌─────────────────┐  │
│  │  Authentication &     │  │  Duplicate Correlation│  │  Civic Priority │  │
│  │  Role-Based Access    │  │  Engine (Deterministic│  │  Scoring Engine │  │
│  └───────────────────────┘  └───────────────────────┘  └─────────────────┘  │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │          Append-Only Cryptographic Ledger (SHA-256 Hash Chain)         │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌───────────────────────┐  ┌───────────────────────┐  ┌─────────────────┐  │
│  │  Case State Machine   │  │  Recurrence Hotspots  │  │  ZIP Evidence   │  │
│  │  & Verification Gate  │  │  Detection            │  │  Export Service │  │
│  └───────────────────────┘  └───────────────────────┘  └─────────────────┘  │
└───────────────────────────────────────┬─────────────────────────────────────┘
                                        │
                         SQLAlchemy 2.0 │ ORM Layer
                                        ▼
                   ┌────────────────────────────────────────┐
                   │ Structured Relational Storage          │
                   │ (SQLite for Dev / PostgreSQL + PostGIS)│
                   └────────────────────────────────────────┘
```

---

## 2. Key Architectural Decisions (ADR)

### ADR 001: Append-Only Event Ledger with Cryptographic Hash Chaining
- **Context:** Standard ticket tracking databases allow privileged administrators to overwrite update timestamps, delete notes, or retroactively change complaint histories.
- **Decision:** Implement an append-only event ledger table (`case_events`) with sequential indexes and cryptographic hash chaining:
  $$\text{Current Hash} = \text{SHA256}(\text{Previous Hash} \parallel \text{Case ID} \parallel \text{Index} \parallel \text{Type} \parallel \text{Canonical JSON Payload})$$
- **Consequences:** Any tampering or row deletion breaks the chain linkage and is immediately flagged by the verification endpoint `/api/v1/cases/{case_id}/events/verify`.

### ADR 002: Deterministic Local Duplicate Detection over Heavy Cloud AI
- **Context:** Civic apps cannot rely on expensive per-query LLM APIs or GPUs during disconnected fieldwork or local deployments.
- **Decision:** Build a deterministic CPU scoring engine using Haversine great-circle distance (35%), normalized Jaccard vocabulary similarity (30%), category identity (20%), and temporal proximity (15%).
- **Consequences:** 100% offline-capable, explainable, testable, and zero operational API costs.

### ADR 003: Separation of Resolution Claim and Verification Outcome
- **Context:** Traditional portals mark a ticket "Closed" when the department operator clicks resolved, silencing the reporter.
- **Decision:** Introduce a formal `AWAITING_VERIFICATION` state between `RESOLUTION_CLAIMED` and `RESOLVED`. Only non-operator citizen observers or community reviewers can transition a case to `RESOLVED` or flag it as `DISPUTED`.
- **Consequences:** Eliminates institutional conflicts of interest and ensures the public record reflects real-world conditions.

---

## 3. Threat Model & Security Posture

| Threat Vector | Mitigation Strategy |
| :--- | :--- |
| **Operator Self-Resolution Fraud** | Server-side role guard prohibits `OPERATOR` role from submitting verification observations on cases. |
| **Credential & Account Compromise** | Passwords hashed using industry-standard bcrypt with salts; JWT tokens signed with HS256 and configurable expirations. |
| **Public PII Exposure** | Citizen identities in public exports and public case APIs are pseudonymized to prevent tracking or retaliation. |
| **Evidence Package Tampering** | Export packages contain canonical `manifest.json` with SHA-256 digests of every constituent file. |
| **Database Row Mutation** | Hash chain re-computations fail if an attacker directly edits event payloads in SQL. |
