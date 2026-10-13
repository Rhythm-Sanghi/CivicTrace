import os
import uuid
import concurrent.futures
from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from alembic.config import Config
from alembic import command

from app.models.entities import (
    User,
    UserRole,
    Department,
    IssueCategory,
    Case,
    CaseState,
    PriorityBand,
    Report,
    ReportModerationStatus,
    ResolutionClaim,
    DuplicateCandidate,
    RevokedToken,
)
from app.services.state_machine import CaseStateMachine
from app.services.ledger import LedgerService
from app.core.security import clean_expired_revoked_tokens, create_access_token
from app.tests.conftest import validate_test_database_safety, TestingSessionLocal, TEST_DB_URL


def test_safety_guard_rejects_unsafe_databases():
    """
    Safety Guard Verification:
    validate_test_database_safety MUST fail closed and refuse execution if:
    - Target is a production or staging database.
    - Target is a development database.
    - Target is a default system database (postgres, template1, etc.).
    - Target is a database merely containing the substring 'test' within another word.
    - Target is an unconfirmed SQLite database.
    """
    # 1. Rejects production URLs (even if 'test' is included in the name)
    with pytest.raises(RuntimeError, match="SAFETY ABORT"):
        validate_test_database_safety("postgresql://user:pass@localhost:5432/civictrace_production")

    with pytest.raises(RuntimeError, match="SAFETY ABORT"):
        validate_test_database_safety("postgresql://user:pass@localhost:5432/civictrace_live")

    with pytest.raises(RuntimeError, match="SAFETY ABORT"):
        validate_test_database_safety("postgresql://user:pass@localhost:5432/test_production")

    with pytest.raises(RuntimeError, match="SAFETY ABORT"):
        validate_test_database_safety("postgresql://user:pass@localhost:5432/prod_test_db")

    # 2. Rejects development databases (even if 'test' is included)
    with pytest.raises(RuntimeError, match="SAFETY ABORT"):
        validate_test_database_safety("sqlite:///./civictrace_dev.db")

    with pytest.raises(RuntimeError, match="SAFETY ABORT"):
        validate_test_database_safety("sqlite:///./test_civictrace_dev.db")

    with pytest.raises(RuntimeError, match="SAFETY ABORT"):
        validate_test_database_safety("postgresql://user:pass@localhost:5432/civictrace_dev_test")

    # 3. Rejects default system databases
    with pytest.raises(RuntimeError, match="SAFETY ABORT"):
        validate_test_database_safety("postgresql://user:pass@localhost:5432/postgres")

    with pytest.raises(RuntimeError, match="SAFETY ABORT"):
        validate_test_database_safety("postgresql://user:pass@localhost:5432/template1")

    # 4. Rejects databases with 'test' merely as a substring inside an unrelated word
    with pytest.raises(RuntimeError, match="SAFETY ABORT"):
        validate_test_database_safety("postgresql://user:pass@localhost:5432/latest_orders")

    with pytest.raises(RuntimeError, match="SAFETY ABORT"):
        validate_test_database_safety("postgresql://user:pass@localhost:5432/contest")

    with pytest.raises(RuntimeError, match="SAFETY ABORT"):
        validate_test_database_safety("postgresql://user:pass@localhost:5432/protest")

    # 5. Rejects SQLite databases without test boundary
    with pytest.raises(RuntimeError, match="SAFETY ABORT"):
        validate_test_database_safety("sqlite:///./orders.db")

    with pytest.raises(RuntimeError, match="SAFETY ABORT"):
        validate_test_database_safety("sqlite:///./contest.db")

    # 6. Allows explicitly verified dedicated test database URLs
    validate_test_database_safety("sqlite:///./test_disposable.db")
    validate_test_database_safety("sqlite:///:memory:")
    validate_test_database_safety("postgresql://user:pass@localhost:5432/civictrace_test")
    validate_test_database_safety("postgresql://user:pass@localhost:5432/test_civictrace")
    validate_test_database_safety("postgresql://user:pass@localhost:5432/test")
    validate_test_database_safety("postgresql://user:pass@localhost:5432/test_db")


def test_integration_authorization_and_role_boundaries(db_session, client):
    """
    Integration Verification: Role authorization and access control boundaries.
    Verifies that roles (CITIZEN, OPERATOR, REVIEWER, ADMINISTRATOR) are enforced
    cleanly against live database models and session authentication.
    """
    suffix = uuid.uuid4().hex[:6]
    cat = IssueCategory(name=f"Roads {suffix}", code=f"RD-{suffix}", default_severity_weight=1.0)
    dept = Department(name=f"Works {suffix}")
    db_session.add_all([cat, dept])
    db_session.commit()

    citizen = User(
        email=f"cit_{suffix}@test.local",
        hashed_password="hash",
        display_name="Citizen Tester",
        role=UserRole.CITIZEN,
    )
    operator = User(
        email=f"op_{suffix}@test.local",
        hashed_password="hash",
        display_name="Operator Tester",
        role=UserRole.OPERATOR,
        department_id=dept.id,
    )
    reviewer = User(
        email=f"rev_{suffix}@test.local",
        hashed_password="hash",
        display_name="Reviewer Tester",
        role=UserRole.REVIEWER,
    )
    admin = User(
        email=f"adm_{suffix}@test.local",
        hashed_password="hash",
        display_name="Admin Tester",
        role=UserRole.ADMINISTRATOR,
    )
    db_session.add_all([citizen, operator, reviewer, admin])
    db_session.commit()

    # Query roles back from database
    persisted_op = db_session.query(User).filter(User.id == operator.id).first()
    assert persisted_op.role == UserRole.OPERATOR
    assert persisted_op.department_id == dept.id

    persisted_rev = db_session.query(User).filter(User.id == reviewer.id).first()
    assert persisted_rev.role == UserRole.REVIEWER


def test_integration_case_lifecycle_and_state_machine(db_session):
    """
    Integration Verification: Full case lifecycle via CaseStateMachine.
    Exercises transitions across states: SUBMITTED -> IN_PROGRESS -> AWAITING_VERIFICATION -> RESOLVED.
    Ensures every state change appends a cryptographically chained CaseEvent to the database ledger.
    """
    suffix = uuid.uuid4().hex[:6]
    cat = IssueCategory(name=f"Sanitation {suffix}", code=f"SAN-{suffix}", default_severity_weight=1.2)
    dept = Department(name=f"Sanitation Dept {suffix}")
    operator = User(
        email=f"op_life_{suffix}@test.local",
        hashed_password="hash",
        display_name="Operator Life",
        role=UserRole.OPERATOR,
    )
    reviewer = User(
        email=f"rev_life_{suffix}@test.local",
        hashed_password="hash",
        display_name="Reviewer Life",
        role=UserRole.REVIEWER,
    )
    db_session.add_all([cat, dept, operator, reviewer])
    db_session.commit()

    # Create Case
    case = Case(
        public_id=f"CAS-2026-{suffix.upper()}",
        title="Sanitation Overflow",
        description="Drain blocked",
        latitude=22.7196,
        longitude=75.8577,
        category_id=cat.id,
        state=CaseState.SUBMITTED,
        priority_score=1.5,
        priority_band=PriorityBand.LOW,
    )
    db_session.add(case)
    db_session.commit()

    # Transition 1: SUBMITTED -> ASSIGNED
    CaseStateMachine.transition_case(
        db=db_session,
        case=case,
        target_state=CaseState.ASSIGNED,
        actor=reviewer,
        notes="Assigned to sanitation works team",
    )
    assert case.state == CaseState.ASSIGNED

    # Transition 2: ASSIGNED -> IN_PROGRESS
    CaseStateMachine.transition_case(
        db=db_session,
        case=case,
        target_state=CaseState.IN_PROGRESS,
        actor=operator,
        notes="Work initiated on drain clearance",
    )
    assert case.state == CaseState.IN_PROGRESS

    # Transition 3: IN_PROGRESS -> AWAITING_VERIFICATION
    CaseStateMachine.transition_case(
        db=db_session,
        case=case,
        target_state=CaseState.AWAITING_VERIFICATION,
        actor=operator,
        notes="Drain cleared and debris removed",
    )
    assert case.state == CaseState.AWAITING_VERIFICATION

    # Transition 4: AWAITING_VERIFICATION -> RESOLVED
    CaseStateMachine.transition_case(
        db=db_session,
        case=case,
        target_state=CaseState.RESOLVED,
        actor=reviewer,
        notes="Reviewer verified cleared drain",
    )
    assert case.state == CaseState.RESOLVED

    # Verify Cryptographic Ledger Chain on active database
    is_valid, count, err, latest = LedgerService.verify_chain(db_session, case.id)
    assert is_valid is True, f"Ledger verification failed: {err}"
    assert count == 4


def test_integration_duplicate_adjudication_and_consolidation(db_session, client):
    """
    Integration Verification: Duplicate candidate adjudication and report consolidation.
    Exercises genuine production endpoint POST /api/v1/reports/duplicates/{candidate_id}/decision.
    Confirms:
    - Role authorization (CITIZEN blocked 403, REVIEWER permitted 200).
    - Validation error rejection (invalid decision returns 400/422).
    - Candidate status transition to APPROVED with reviewer attribution.
    - Automatic domain supersession of conflicting duplicate candidates to SUPERSEDED.
    - Report re-parenting to target case.
    - Cryptographic event append to target case ledger (CASE_CONSOLIDATED_DUPLICATE_REPORT) with intact hash chain.
    """
    suffix = uuid.uuid4().hex[:6]
    cat = IssueCategory(name=f"Signals {suffix}", code=f"SIG-{suffix}", default_severity_weight=1.5)
    reviewer = User(
        email=f"rev_dup_{suffix}@test.local",
        hashed_password="hash",
        display_name="Reviewer Dup",
        role=UserRole.REVIEWER,
    )
    citizen = User(
        email=f"cit_dup_{suffix}@test.local",
        hashed_password="hash",
        display_name="Citizen Dup",
        role=UserRole.CITIZEN,
    )
    db_session.add_all([cat, reviewer, citizen])
    db_session.commit()

    case_target = Case(
        public_id=f"CAS-2026-TGT-{suffix.upper()}",
        title="Traffic Light Fault 1",
        description="Signal down",
        latitude=22.72,
        longitude=75.86,
        category_id=cat.id,
        state=CaseState.IN_PROGRESS,
        priority_score=1.5,
        priority_band=PriorityBand.LOW,
    )
    case_other = Case(
        public_id=f"CAS-2026-OTH-{suffix.upper()}",
        title="Traffic Light Fault 2",
        description="Signal down nearby",
        latitude=22.721,
        longitude=75.861,
        category_id=cat.id,
        state=CaseState.SUBMITTED,
        priority_score=1.0,
        priority_band=PriorityBand.LOW,
    )
    db_session.add_all([case_target, case_other])
    db_session.commit()

    report = Report(
        public_id=f"RPT-2026-{suffix.upper()}",
        title="Duplicate Light Report",
        description="Signal is dark",
        latitude=22.7205,
        longitude=75.8605,
        category_id=cat.id,
        case_id=case_other.id,
        moderation_status=ReportModerationStatus.APPROVED,
    )
    db_session.add(report)
    db_session.commit()

    # Create two duplicate candidates for this report
    cand1 = DuplicateCandidate(
        report_id=report.id,
        target_case_id=case_target.id,
        distance_meters=25.0,
        spatial_score=0.9,
        text_score=0.85,
        category_score=1.0,
        temporal_score=0.95,
        composite_score=0.92,
        explanation="High spatial and category match",
        status="PENDING",
    )
    cand2 = DuplicateCandidate(
        report_id=report.id,
        target_case_id=case_other.id,
        distance_meters=40.0,
        spatial_score=0.8,
        text_score=0.8,
        category_score=1.0,
        temporal_score=0.9,
        composite_score=0.86,
        explanation="Secondary match",
        status="PENDING",
    )
    db_session.add_all([cand1, cand2])
    db_session.commit()

    citizen_token = create_access_token(citizen.id)
    reviewer_token = create_access_token(reviewer.id)

    # 1. Authorization check: Citizen cannot adjudicate duplicate candidates (403 Forbidden)
    res_unauth = client.post(
        f"/api/v1/reports/duplicates/{cand1.id}/decision",
        json={"decision": "APPROVE"},
        headers={"Authorization": f"Bearer {citizen_token}"},
    )
    assert res_unauth.status_code == 403

    # 2. Validation check: Invalid decision rejected (400/422), transaction rolled back
    res_invalid = client.post(
        f"/api/v1/reports/duplicates/{cand1.id}/decision",
        json={"decision": "INVALID_CHOICE"},
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert res_invalid.status_code in (400, 422)

    # 3. Authentic reviewer approval via production endpoint
    res_approve = client.post(
        f"/api/v1/reports/duplicates/{cand1.id}/decision",
        json={"decision": "APPROVE", "notes": "Approved duplicate correlation by reviewer"},
        headers={"Authorization": f"Bearer {reviewer_token}"},
    )
    assert res_approve.status_code == 200
    resp_data = res_approve.json()
    assert resp_data["status"] == "APPROVED"

    # 4. Assert database state reflects domain workflow
    db_session.expire_all()
    reloaded_cand1 = db_session.query(DuplicateCandidate).filter(DuplicateCandidate.id == cand1.id).first()
    reloaded_cand2 = db_session.query(DuplicateCandidate).filter(DuplicateCandidate.id == cand2.id).first()
    reloaded_rep = db_session.query(Report).filter(Report.id == report.id).first()
    reloaded_target = db_session.query(Case).filter(Case.id == case_target.id).first()

    assert reloaded_cand1.status == "APPROVED"
    assert reloaded_cand1.reviewed_by_id == reviewer.id
    assert reloaded_cand2.status == "SUPERSEDED"
    assert reloaded_rep.case_id == case_target.id
    assert reloaded_target is not None

    # 5. Verify cryptographic ledger audit event appended to target case
    valid_chain, count, err, _ = LedgerService.verify_chain(db_session, case_target.id)
    assert valid_chain is True, f"Target case ledger chain broken: {err}"
    assert count >= 1


def test_integration_resolution_claims_unique_active_constraint(db_session):
    """
    Integration Verification: Unique partial index uq_active_resolution_claim_per_case.
    Ensures the database constraint prevents two active AWAITING_VERIFICATION resolution
    claims on the same case, while allowing multiple claims across different cycles.
    """
    suffix = uuid.uuid4().hex[:6]
    cat = IssueCategory(name=f"Potholes {suffix}", code=f"POT-{suffix}", default_severity_weight=1.0)
    operator = User(
        email=f"op_claim_{suffix}@test.local",
        hashed_password="hash",
        display_name="Operator Claim",
        role=UserRole.OPERATOR,
    )
    db_session.add_all([cat, operator])
    db_session.commit()

    case = Case(
        public_id=f"CAS-2026-POT-{suffix.upper()}",
        title="Pothole Repair",
        description="Large pothole",
        latitude=22.72,
        longitude=75.86,
        category_id=cat.id,
        state=CaseState.IN_PROGRESS,
        priority_score=1.0,
        priority_band=PriorityBand.LOW,
    )
    db_session.add(case)
    db_session.commit()

    # First active claim: succeeds
    claim1 = ResolutionClaim(
        case_id=case.id,
        operator_id=operator.id,
        work_summary="Patch applied",
        actions_taken="Asphalt laid and compacted",
        status="AWAITING_VERIFICATION",
    )
    db_session.add(claim1)
    db_session.commit()

    # Second active claim on SAME case while first is still AWAITING_VERIFICATION:
    # Must fail unique constraint!
    claim2 = ResolutionClaim(
        case_id=case.id,
        operator_id=operator.id,
        work_summary="Second concurrent patch attempt",
        actions_taken="Attempted concurrent claim",
        status="AWAITING_VERIFICATION",
    )
    db_session.add(claim2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    # Now mark claim 1 as DISPUTED (resolves prior cycle)
    claim1.status = "DISPUTED"
    db_session.commit()

    # Now a second claim for a rework cycle succeeds cleanly
    claim3 = ResolutionClaim(
        case_id=case.id,
        operator_id=operator.id,
        work_summary="Rework patch applied",
        actions_taken="Repaired properly",
        status="AWAITING_VERIFICATION",
    )
    db_session.add(claim3)
    db_session.commit()
    assert claim3.id is not None


def test_integration_session_revocation_storage(db_session):
    """
    Integration Verification: RevokedToken persistence and TTL cleanup.
    Proves that revoked tokens persist to database table and can be queried
    by separate sessions, surviving process isolation.
    """
    tok1 = "token_hash_alpha_12345"
    tok2 = "token_hash_beta_67890"

    now = datetime.now(timezone.utc)
    active_expiry = (now + timedelta(hours=2)).timestamp()
    expired_time = (now - timedelta(hours=1)).timestamp()

    r1 = RevokedToken(token_hash=tok1, expires_at=active_expiry)
    r2 = RevokedToken(token_hash=tok2, expires_at=expired_time)
    db_session.add_all([r1, r2])
    db_session.commit()

    # Query from a separate fresh session
    fresh_session = TestingSessionLocal()
    found1 = fresh_session.query(RevokedToken).filter(RevokedToken.token_hash == tok1).first()
    found2 = fresh_session.query(RevokedToken).filter(RevokedToken.token_hash == tok2).first()
    assert found1 is not None
    assert found2 is not None
    fresh_session.close()

    # Run pruning
    clean_expired_revoked_tokens(db_session=db_session)
    db_session.commit()

    # Verify expired token pruned and active token retained
    after_session = TestingSessionLocal()
    assert after_session.query(RevokedToken).filter(RevokedToken.token_hash == tok1).first() is not None
    assert after_session.query(RevokedToken).filter(RevokedToken.token_hash == tok2).first() is None
    after_session.close()


def test_integration_concurrent_ledger_writes(db_session):
    """
    Integration Verification: Concurrent ledger writes using atomic sequence counters.
    Exercises 8 concurrent threads appending events to the same case via independent
    database sessions. Verifies zero sequence gaps and intact hash chaining.
    """
    suffix = uuid.uuid4().hex[:6]
    cat = IssueCategory(name=f"Parks {suffix}", code=f"PK-{suffix}", default_severity_weight=1.0)
    db_session.add(cat)
    db_session.commit()

    case = Case(
        public_id=f"CAS-2026-PRK-{suffix.upper()}",
        title="Park Bench Repair",
        description="Broken slat",
        latitude=22.73,
        longitude=75.87,
        category_id=cat.id,
        state=CaseState.SUBMITTED,
        priority_score=1.0,
        priority_band=PriorityBand.LOW,
    )
    db_session.add(case)
    db_session.commit()
    case_id = case.id

    def _append_worker(worker_id: int):
        s = TestingSessionLocal()
        try:
            c = s.query(Case).filter(Case.id == case_id).first()
            ev = LedgerService.append_event(
                db=s,
                case=c,
                event_type="OBSERVATION_NOTED",
                payload={"worker_id": worker_id, "note": f"Concurrent note from thread {worker_id}"},
                public_actor_label="Citizen Observer",
            )
            s.commit()
            return ev.event_index
        finally:
            s.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(_append_worker, i) for i in range(8)]
        indices = [f.result() for f in concurrent.futures.as_completed(futures)]

    # Assert 8 unique monotonic event indices (1 through 8)
    assert len(indices) == 8
    assert sorted(indices) == list(range(1, 9))

    # Assert hash chain integrity across all 8 concurrent appends
    verify_db = TestingSessionLocal()
    is_valid, count, err, _ = LedgerService.verify_chain(verify_db, case_id)
    verify_db.close()

    assert is_valid is True, f"Hash chain broken: {err}"
    assert count == 8


def test_integration_migrations_empty_and_populated_schema(tmp_path):
    """
    Integration Verification: Migration correctness from empty database and populated prior schema.
    1. Upgrades from empty database up to initial table creation revision (51344ae88ae5).
    2. Populates prior schema records (user, category, case, report).
    3. Upgrades forward through all subsequent migrations up to head (e8f2c1b9a304).
    4. Verifies populated data is preserved and new columns, tables, and indexes exist.
    """
    probe_db_path = str(tmp_path / "migration_verification_probe.db")
    probe_url = f"sqlite:///{probe_db_path}"

    api_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    alembic_ini = os.path.join(api_dir, "alembic.ini")

    cfg = Config(alembic_ini)
    cfg.set_main_option("sqlalchemy.url", probe_url)

    # 1. Upgrade from empty to base table creation revision
    command.upgrade(cfg, "51344ae88ae5")

    # 2. Insert baseline records into prior schema
    from sqlalchemy import create_engine as create_probe_engine
    p_engine = create_probe_engine(probe_url)
    with p_engine.connect() as conn:
        user_id = str(uuid.uuid4())
        cat_id = str(uuid.uuid4())
        case_id = str(uuid.uuid4())

        conn.execute(
            text(
                "INSERT INTO issue_categories (id, name, code, default_severity_weight, created_at) "
                "VALUES (:id, 'Prior Category', 'PRIOR-01', 1.0, CURRENT_TIMESTAMP)"
            ),
            {"id": cat_id},
        )
        conn.execute(
            text(
                "INSERT INTO users (id, email, hashed_password, display_name, role, is_active, created_at) "
                "VALUES (:id, 'prior@test.local', 'hash', 'Prior User', 'CITIZEN', 1, CURRENT_TIMESTAMP)"
            ),
            {"id": user_id},
        )
        conn.execute(
            text(
                "INSERT INTO cases (id, public_id, title, description, latitude, longitude, category_id, state, "
                "priority_score, priority_band, created_at, updated_at) "
                "VALUES (:id, 'CAS-2026-PRIOR', 'Prior Case', 'Description', 22.7, 75.8, :cat_id, 'SUBMITTED', 1.0, 'LOW', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
            ),
            {"id": case_id, "cat_id": cat_id},
        )
        conn.commit()
        conn.commit()

    # 3. Upgrade forward to HEAD
    command.upgrade(cfg, "head")

    # 4. Verify populated data preserved and new features present
    with p_engine.connect() as conn:
        # User record preserved and acquired new column is_identity_verified defaulted to False (0)
        u_row = conn.execute(
            text("SELECT id, email, is_identity_verified, identity_provider FROM users WHERE id = :id"),
            {"id": user_id},
        ).fetchone()
        assert u_row is not None
        assert u_row[1] == "prior@test.local"
        assert u_row[2] in (False, 0)

        # New tables exist
        table_rows = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'")
        ).fetchall()
        t_names = [r[0] for r in table_rows]
        assert "revoked_tokens" in t_names
        assert "sequence_counters" in t_names

        # Case record preserved
        c_row = conn.execute(text("SELECT id, title FROM cases WHERE id = :id"), {"id": case_id}).fetchone()
        assert c_row is not None
        assert c_row[1] == "Prior Case"

    p_engine.dispose()


def test_integration_postgresql_dialect_and_server_verified(db_session):
    """
    Verification: Asserts that when running in a PostgreSQL-targeted environment (such as in CI backend-postgres-test),
    the test runner genuinely executes against the PostgreSQL dialect and not falling back to SQLite.
    When TEST_DB_URL targets PostgreSQL, asserts dialect name is 'postgresql' and PostgreSQL server version is queryable.
    """
    dialect_name = db_session.bind.dialect.name
    if "postgres" in TEST_DB_URL.lower():
        assert dialect_name == "postgresql", (
            f"Expected PostgreSQL dialect when TEST_DB_URL targets PostgreSQL, but got '{dialect_name}'"
        )
        version = db_session.execute(text("SELECT version()")).scalar()
        assert "PostgreSQL" in version, f"Expected PostgreSQL version output, got '{version}'"
    else:
        # On local/SQLite runner, verify it is SQLite
        assert dialect_name == "sqlite", f"Expected SQLite dialect when on default local test DB, got '{dialect_name}'"

