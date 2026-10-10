from sqlalchemy.orm import Session
from app.models.entities import Report, Case

def allocate_report_public_id(db: Session, year: int = 2026) -> str:
    """
    Allocates a monotonic, collision-resistant public report reference:
    e.g. RPT-2026-0001, RPT-2026-0002...
    Extracts the highest current sequential numeric suffix to prevent reuse on record deletion.
    """
    latest_report = (
        db.query(Report)
        .filter(Report.public_id.like(f"RPT-{year}-%"))
        .order_by(Report.created_at.desc(), Report.public_id.desc())
        .first()
    )
    if not latest_report:
        return f"RPT-{year}-0001"

    try:
        current_num = int(latest_report.public_id.split("-")[-1])
        next_num = current_num + 1
    except (ValueError, IndexError):
        next_num = db.query(Report).count() + 1

    # Collision guard
    while db.query(Report).filter(Report.public_id == f"RPT-{year}-{next_num:04d}").first():
        next_num += 1

    return f"RPT-{year}-{next_num:04d}"

def allocate_case_public_id(db: Session, year: int = 2026) -> str:
    """
    Allocates a monotonic, collision-resistant public case reference:
    e.g. CAS-2026-0001, CAS-2026-0002...
    Extracts the highest current sequential numeric suffix to prevent reuse on record deletion.
    """
    latest_case = (
        db.query(Case)
        .filter(Case.public_id.like(f"CAS-{year}-%"))
        .order_by(Case.created_at.desc(), Case.public_id.desc())
        .first()
    )
    if not latest_case:
        return f"CAS-{year}-0001"

    try:
        current_num = int(latest_case.public_id.split("-")[-1])
        next_num = current_num + 1
    except (ValueError, IndexError):
        next_num = db.query(Case).count() + 1

    # Collision guard
    while db.query(Case).filter(Case.public_id == f"CAS-{year}-{next_num:04d}").first():
        next_num += 1

    return f"CAS-{year}-{next_num:04d}"
