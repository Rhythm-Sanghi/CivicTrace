# CivicTrace Security Review & Threat Model Audit

**Date:** October 2026  
**Auditor Role:** Principal Security Engineer & Database Architect  
**Evaluation Scope:** Cryptographic Integrity, RBAC, Multi-Process Concurrency, Database-Backed Session Revocation, Evidence Confinement, Package Authenticity, and State Transitions.

---

## 1. Executive Summary

CivicTrace is an open-source civic infrastructure reporting and public accountability system designed for zero-external-dependency local execution (SQLite) and enterprise multi-user deployment (PostgreSQL/PostGIS).

This comprehensive hardening cycle reviewed and remediated critical business logic vulnerabilities, state machine bypasses, ledger validation limitations, session token invalidation gaps, multiprocess sequence races, and client-side access control boundaries across all 35 audit findings.

---

## 2. Security Guarantees & Cryptographic Architecture

### 2.1 Append-Only Cryptographic Event Ledger
- **SHA-256 Hash Chaining:** Every case state change, department assignment, duplicate correlation, and verification vote appends a cryptographically chained `CaseEvent`.
- **Preimage Format:** Standardized canonical representation binds `previous_hash`, `case_id`, `event_index`, `event_type`, and `canonical_json(payload)`.
- **Independent Checkpointing & Ed25519 Signatures:** Checkpoints aggregate the global state root of all recorded events and sign the root using offline Ed25519 digital signatures. Verifiers can validate checkpoints using the public key without needing database write access.
- **Realistic Trust Boundary Note:** While hash-chaining guarantees detection of history tampering or payload alteration by database observers, an administrator with full write access to the database storage can rewrite the entire chain unless state roots are independently anchored to external checkpoints or public keys.

### 2.2 Package Authenticity & Fail-Closed Modes
The archive verification system defines two mutually exclusive modes:
1. **File Integrity Mode (`VerificationMode.FILE_INTEGRITY`):**
   - Validates internal archive structure, zip bombs, path traversal (`..`), duplicate zip members, extra undeclared files, and SHA-256 hashes against `manifest.json`.
   - Never claims independent external authenticity.
2. **Trusted Authenticity Mode (`VerificationMode.TRUSTED_AUTHENTICITY`):**
   - Requires an explicit trusted external public key (`expected_public_key`) or trusted checkpoint state root (`trusted_checkpoint_root`).
   - Fails closed immediately if trusted external material is omitted (refuses to silently downgrade to hash-only verification).
   - Rejects key replacement attacks: if an attacker modifies the package and re-signs the manifest with an arbitrary key, the verifier rejects the payload because the manifest public key diverges from the trust anchor.
   - Verifies timeline continuity and hash chaining across all events in `event_ledger.json`.

### 2.3 Database-Backed Session Management & Token Revocation
- **Cookie-Based Authentication:** Tokens are transmitted via secure `HttpOnly` session cookies with `SameSite=Lax` protection against cross-site script reading.
- **Double Submit CSRF Protection:** Mutating requests using cookie authentication require matching `ct_csrf` cookie and `X-CSRF-Token` header.
- **Database-Backed Revocation Table:** Revoked JWT IDs are stored in the database table `revoked_tokens` with expiration timestamps.
- **Cross-Process Consistency:** Survives service restarts and synchronizes instantly across multiple worker processes without relying on vulnerable in-memory process caches.
- **Automated TTL Pruning:** Expired entries are pruned safely via `clean_expired_revoked_tokens()`.

### 2.4 Evidence Asset Storage & Confinement
- **Storage Boundary Confinement:** All evidence uploads and downloads are strictly confined to `settings.UPLOAD_DIR` using `Path.resolve().is_relative_to()`. Path traversal characters (`../`) are safely rejected with 403 Forbidden.
- **Magic Bytes Verification:** File contents are verified using header magic bytes (JPEG `\xFF\xD8\xFF`, PNG `\x89PNG\r\n\x1A\n`, WebP `RIFF....WEBP`, PDF `%PDF`).
- **Access Control:** Pending or unapproved evidence assets are restricted to the original reporter and authorized reviewers/administrators. Unapproved media is hidden from public downloads and dossiers.
- **Guest Upload Capability Security:** Guest reports issue a one-way capability token. Only the SHA-256 hash is stored in the database. Tokens expire after 120 minutes, are revokable upon moderation rejection, and are verified using constant-time `hmac.compare_digest`. Tokens are transmitted via `X-Upload-Token` header.

### 2.5 Multi-Process Concurrency & Database-Enforced Identifiers
- Replaced Python process global thread lock (`_sequence_lock`) with durable database-level sequence allocation (`sequence_counters` table).
- Atomic allocation uses `INSERT ... ON CONFLICT (name) DO UPDATE SET current_val = sequence_counters.current_val + 1 RETURNING current_val`.
- Guaranteed collision-free, monotonic sequence numbering across multiple separate operating system processes and worker instances.
- Proven safe under simultaneous multiprocess write contention with independent database sessions; sequence numbers are durable and never reused upon record deletion.

---

## 3. Workflow Safeguards & Anti-Abuse Policies

### 3.1 Operator Scope & Conflict-of-Interest Guard
- Department operators can only transition cases or file resolution claims for cases assigned to their matching department (`operator.department_id == assignment.department_id`).
- Operators are strictly blocked by role check from submitting citizen verification observations for their own or other department repair claims.

### 3.2 Verification Quorum & Dispute Safeguards
- **Active Claim Cycle:** Verification observations are strictly scoped to the active `ResolutionClaim`. Stale confirmations from previous cycles are excluded.
- **Dispute Precedence:** An unresolved dispute (`STILL_UNRESOLVED`) blocks automatic resolution. Once disputed, later positive confirmations cannot silently overwrite the dispute or close the case. Only explicit Reviewer/Administrator adjudication or an operator rework cycle can advance the case.
- **Identity Assurance Disclaimer:** Distinct self-registered email accounts are authenticated, but offline systems without external identity providers cannot mathematically eliminate Sybil account creation. The application adopts a conservative policy: controversial or disputed cases require Reviewer sign-off rather than automated closure.

### 3.3 Production Moderation Defaults
- In production (`REQUIRE_REPORT_MODERATION=True`), reports submitted by citizens or guests start in `PENDING` moderation.
- Pending reports are strictly quarantined from public listing (`GET /reports`) and public case generation until approved by an authorized Reviewer.
- Reviewer moderation actions are audited and update case statistics dynamically.

---

## 4. Verification Evidence & Test Suite Summary

- **Backend Pytest Suite:** 55 passing automated tests (`$env:PYTHONPATH="services/api"; pytest services/api/app/tests -v`) covering:
  - Multiprocess sequence allocator concurrency and monotonic uniqueness
  - Guest capability upload security, expiry, revocation, and header enforcement
  - Session revocation persistence across restarts and cross-worker validation
  - Digital signature verification and key replacement attack rejection
  - Event ledger hash preimage validation and timeline tamper detection
  - Complete 9-vector ledger authenticity attack suite (`test_ledger_authenticity_attacks.py`)
  - 8-scenario database concurrency race suite (`test_workflow_concurrency.py`)
  - State machine atomic transitions and ledger recording
  - Quorum verification policies, active claim isolation, dispute blocking, and Sybil resistance (`test_verification_safeguards.py`)
  - Rate limiting sliding windows and accurate `Retry-After` calculation
- **Frontend Vitest Suite:** 7 passing unit & regression tests (`npm test` in `apps/web`) covering components, authentication forms, reviewer moderation desk, operator claims station, and responsive accessibility.
- **Playwright Chromium E2E:** 14 full interactive browser lifecycle steps + unauthorized operator check + evidence package tamper detection + 320px mobile viewport, keyboard navigation, and 200% zoom checks (`scripts/run_browser_e2e.py`).
- **Database Migrations:** Clean forward schema migration verified from empty database (`alembic upgrade head`) and data-preserving upgrade of existing development datasets to Alembic head `c7a3b4e12f01`.
- **Operational Release Utility:** Atomic backup, restore verification, upload cleanup, and Ed25519 keypair rotation automated in `scripts/backup_restore.py`.
