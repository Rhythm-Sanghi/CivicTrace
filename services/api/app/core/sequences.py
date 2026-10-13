import time
import random
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError, DBAPIError
from app.models.entities import Report, Case, CaseEvent, SequenceCounter


def _get_max_report_num(db: Session, year: int) -> int:
    prefix = f"RPT-{year}-"
    reports = db.query(Report.public_id).filter(Report.public_id.like(f"{prefix}%")).all()
    max_num = 0
    for (pid,) in reports:
        try:
            val = int(pid.split("-")[-1])
            if val > max_num:
                max_num = val
        except (ValueError, IndexError):
            pass
    return max_num


def _get_max_case_num(db: Session, year: int) -> int:
    prefix = f"CAS-{year}-"
    cases = db.query(Case.public_id).filter(Case.public_id.like(f"{prefix}%")).all()
    max_num = 0
    for (pid,) in cases:
        try:
            val = int(pid.split("-")[-1])
            if val > max_num:
                max_num = val
        except (ValueError, IndexError):
            pass
    return max_num


def _get_max_case_event_index(db: Session, case_id: str) -> int:
    last = (
        db.query(CaseEvent.event_index)
        .filter(CaseEvent.case_id == case_id)
        .order_by(CaseEvent.event_index.desc())
        .first()
    )
    return last[0] if last else 0


def allocate_atomic_counter(db: Session, name: str, fallback_initial: int) -> int:
    """
    Executes an atomic SQL allocation on sequence_counters table:
    Works on PostgreSQL and SQLite (>=3.35) using ON CONFLICT DO UPDATE ... RETURNING.
    Handles multi-process concurrency with transient lock contention backoff.
    """
    sql = text("""
        INSERT INTO sequence_counters (name, next_value, updated_at)
        VALUES (:name, :initial_val + 1, :now)
        ON CONFLICT(name) DO UPDATE
        SET next_value = sequence_counters.next_value + 1, updated_at = :now
        RETURNING sequence_counters.next_value - 1
    """)
    now = datetime.now(timezone.utc)
    max_retries = 25
    for attempt in range(max_retries):
        try:
            result = db.execute(
                sql, {"name": name, "initial_val": fallback_initial, "now": now}
            ).fetchone()
            if result:
                return int(result[0])
            break
        except (OperationalError, DBAPIError) as e:
            err_msg = str(e).lower()
            if "locked" in err_msg or "busy" in err_msg:
                time.sleep(0.015 * (1.5 ** min(attempt, 6)) + random.uniform(0.005, 0.02))
                continue
            raise

    # Fallback in case RETURNING is not supported by legacy driver or connection
    sc = db.query(SequenceCounter).filter(SequenceCounter.name == name).with_for_update().first()
    if not sc:
        sc = SequenceCounter(name=name, next_value=fallback_initial + 1, updated_at=now)
        db.add(sc)
        db.flush()
        return fallback_initial
    allocated = sc.next_value
    sc.next_value += 1
    sc.updated_at = now
    db.flush()
    return allocated


def allocate_report_public_id(db: Session, year: Optional[int] = None) -> str:
    """
    Allocates a monotonic, collision-resistant public report reference:
    e.g. RPT-2026-0001, RPT-2026-0002...
    Enforced by database sequence_counters table and unique constraint on reports.public_id.
    Guarantees no reuse after record deletion and multi-process coordination.
    """
    if year is None:
        year = datetime.now(timezone.utc).year

    name = f"report_{year}"
    existing_counter = db.query(SequenceCounter).filter(SequenceCounter.name == name).first()
    initial_default = 1
    if not existing_counter:
        max_existing = _get_max_report_num(db, year)
        initial_default = max_existing + 1 if max_existing > 0 else 1

    allocated_num = allocate_atomic_counter(db, name, fallback_initial=initial_default)
    return f"RPT-{year}-{allocated_num:04d}"


def allocate_case_public_id(db: Session, year: Optional[int] = None) -> str:
    """
    Allocates a monotonic, collision-resistant public case reference:
    e.g. CAS-2026-0001, CAS-2026-0002...
    Enforced by database sequence_counters table and unique constraint on cases.public_id.
    Guarantees no reuse after record deletion and multi-process coordination.
    """
    if year is None:
        year = datetime.now(timezone.utc).year

    name = f"case_{year}"
    existing_counter = db.query(SequenceCounter).filter(SequenceCounter.name == name).first()
    initial_default = 1
    if not existing_counter:
        max_existing = _get_max_case_num(db, year)
        initial_default = max_existing + 1 if max_existing > 0 else 1

    allocated_num = allocate_atomic_counter(db, name, fallback_initial=initial_default)
    return f"CAS-{year}-{allocated_num:04d}"


def allocate_case_event_index(db: Session, case_id: str) -> int:
    """
    Allocates the next monotonic 1-based sequential event index for a specific case.
    Guarantees separate, safe per-case event sequence coordination across multiple worker processes.
    """
    name = f"case_event_{case_id}"
    existing_counter = db.query(SequenceCounter).filter(SequenceCounter.name == name).first()
    initial_default = 1
    if not existing_counter:
        max_existing = _get_max_case_event_index(db, case_id)
        initial_default = max_existing + 1 if max_existing > 0 else 1

    return allocate_atomic_counter(db, name, fallback_initial=initial_default)
