from datetime import datetime, timezone, timedelta
from app.db.session import SessionLocal, Base, engine
from app.core.security import get_password_hash
from app.models.entities import (
    User,
    UserRole,
    Department,
    ServiceArea,
    IssueCategory,
    Report,
    Case,
    CaseState,
    ReportModerationStatus,
    PriorityBand,
    DuplicateCandidate,
    ResolutionClaim,
    VerificationObservation,
    VerificationOutcome,
    RecurrenceRelationship,
)
from app.services.ledger import LedgerService
from app.services.priority_engine import PriorityEngine
from app.services.duplicate_engine import DuplicateDetectionEngine

def seed_database(reset: bool = False):
    if reset:
        Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # Check if already seeded
        if db.query(User).filter(User.email == "admin@civictrace.local").first():
            print("Database already contains seed accounts. Skipping seeding.")
            return

        print("Seeding CivicTrace with realistic Indore civic infrastructure scenarios...")

        # 1. Service Area
        service_area = ServiceArea(
            name="Indore Central Ward",
            city="Indore",
            center_latitude=22.7196,
            center_longitude=75.8577,
        )
        db.add(service_area)
        db.flush()

        # 2. Departments
        dept_roads = Department(
            name="Indore Municipal Corp - Road Maintenance",
            description="Responsible for arterial road paving, potholes, and sidewalks",
            service_area_id=service_area.id,
        )
        dept_lighting = Department(
            name="Indore Municipal Corp - Public Lighting Division",
            description="Responsible for street illumination and electrical safety",
            service_area_id=service_area.id,
        )
        dept_water = Department(
            name="Indore Municipal Corp - Water Supply & Drainage",
            description="Manages municipal pipelines, drainage, and leak fixes",
            service_area_id=service_area.id,
        )
        db.add_all([dept_roads, dept_lighting, dept_water])
        db.flush()

        # 3. Standard Users for all four roles
        # Administrator
        admin_user = User(
            email="admin@civictrace.local",
            hashed_password=get_password_hash("AdminPass2026!"),
            display_name="Devi Ahilya Admin",
            role=UserRole.ADMINISTRATOR,
        )
        # Community Reviewer
        reviewer_user = User(
            email="reviewer@civictrace.local",
            hashed_password=get_password_hash("ReviewerPass2026!"),
            display_name="Rajesh Sharma (Reviewer)",
            role=UserRole.REVIEWER,
        )
        # Department Operators
        operator_roads = User(
            email="roads.operator@civictrace.local",
            hashed_password=get_password_hash("OperatorPass2026!"),
            display_name="Anil Verma (Road Works)",
            role=UserRole.OPERATOR,
            department_id=dept_roads.id,
        )
        operator_lighting = User(
            email="lighting.operator@civictrace.local",
            hashed_password=get_password_hash("OperatorPass2026!"),
            display_name="Kavita Jain (Lighting Ops)",
            role=UserRole.OPERATOR,
            department_id=dept_lighting.id,
        )
        # Citizens
        citizen_1 = User(
            email="citizen.aarav@civictrace.local",
            hashed_password=get_password_hash("CitizenPass2026!"),
            display_name="Aarav Mehta",
            role=UserRole.CITIZEN,
        )
        citizen_2 = User(
            email="citizen.priya@civictrace.local",
            hashed_password=get_password_hash("CitizenPass2026!"),
            display_name="Priya Patel",
            role=UserRole.CITIZEN,
        )
        db.add_all([admin_user, reviewer_user, operator_roads, operator_lighting, citizen_1, citizen_2])
        db.flush()

        # 4. Issue Categories
        cat_pothole = IssueCategory(
            name="Potholes and Damaged Roads",
            code="ROAD_HAZARD",
            description="Craters, road subsidence, broken asphalt, and sidewalk gaps",
            default_severity_weight=2.5,
        )
        cat_lighting = IssueCategory(
            name="Broken Streetlights",
            code="LIGHTING_FAILURE",
            description="Dark transit corridors, unlit intersections, and fixture faults",
            default_severity_weight=2.0,
        )
        cat_water = IssueCategory(
            name="Water Leaks & Pipe Bursts",
            code="WATER_LEAK",
            description="Municipal line leaks, road flooding, and potable water waste",
            default_severity_weight=2.8,
        )
        cat_electrical = IssueCategory(
            name="Dangerous Electrical Infrastructure",
            code="ELECTRICAL_HAZARD",
            description="Exposed live wires, damaged distribution boxes, electrocution risk",
            default_severity_weight=3.8,
        )
        cat_waste = IssueCategory(
            name="Waste Collection Failures",
            code="WASTE_OVERFLOW",
            description="Commercial garbage overflow, obstructed public rights of way",
            default_severity_weight=1.5,
        )
        db.add_all([cat_pothole, cat_lighting, cat_water, cat_electrical, cat_waste])
        db.flush()

        now = datetime.now(timezone.utc)

        # -------------------------------------------------------------
        # SCENARIO A — Duplicate Reports Consolidating into One Case
        # 3 citizens separately report the same damaged road on MG Road near Rajwada
        # -------------------------------------------------------------
        score_a, band_a, breakdown_a = PriorityEngine.calculate_priority(
            category_weight=cat_pothole.default_severity_weight,
            report_count=3,
            created_at=now - timedelta(days=2),
        )
        case_a = Case(
            public_id="CAS-2026-0001",
            category_id=cat_pothole.id,
            service_area_id=service_area.id,
            title="Severe asphalt subsidence and deep crater on MG Road",
            description="Deep 15-inch crater near Rajwada intersection creating severe risk for two-wheelers and buses.",
            latitude=22.7188,
            longitude=75.8562,
            address_reference="MG Road, near Rajwada Chowk, Indore",
            state=CaseState.VERIFIED,
            priority_score=score_a,
            priority_band=band_a,
            priority_breakdown=breakdown_a,
            created_at=now - timedelta(days=2),
            verified_at=now - timedelta(days=1),
        )
        db.add(case_a)
        db.flush()

        rpt_a1 = Report(
            public_id="RPT-2026-0001",
            category_id=cat_pothole.id,
            reporter_id=citizen_1.id,
            title="Dangerous pothole on MG Road crossing",
            description="Large crater forming in the middle of the road right before Rajwada market.",
            latitude=22.7188,
            longitude=75.8562,
            address_reference="MG Road near Rajwada",
            case_id=case_a.id,
            created_at=now - timedelta(days=2),
        )
        rpt_a2 = Report(
            public_id="RPT-2026-0002",
            category_id=cat_pothole.id,
            reporter_id=citizen_2.id,
            title="Deep road hole causing traffic disruption on MG Road",
            description="Heavy crater near Rajwada intersection, cars swerving into oncoming traffic.",
            latitude=22.7189,
            longitude=75.8563,
            address_reference="Opposite Rajwada Palace",
            case_id=case_a.id,
            created_at=now - timedelta(days=1, hours=18),
        )
        rpt_a3 = Report(
            public_id="RPT-2026-0003",
            category_id=cat_pothole.id,
            guest_pseudonym="Vikas Dubey (Local Merchant)",
            title="Asphalt crater on MG Road worsening after rain",
            description="The pothole in front of the cloth market is now 1.5 feet deep. Multiple scooter slips today.",
            latitude=22.7187,
            longitude=75.8561,
            address_reference="Cloth Market junction, MG Road",
            case_id=case_a.id,
            created_at=now - timedelta(days=1, hours=4),
        )
        db.add_all([rpt_a1, rpt_a2, rpt_a3])
        db.flush()

        LedgerService.append_event(
            db=db,
            case=case_a,
            event_type="REPORT_CREATED",
            payload={"report_id": rpt_a1.public_id, "title": rpt_a1.title},
            actor=citizen_1,
            public_actor_label="Citizen Aarav Mehta",
        )
        LedgerService.append_event(
            db=db,
            case=case_a,
            event_type="REPORT_LINKED",
            payload={"report_id": rpt_a2.public_id, "reason": "Deterministic duplicate detection: 92% similarity (14m away)"},
            actor=reviewer_user,
            public_actor_label="Community Reviewer Rajesh Sharma",
        )
        LedgerService.append_event(
            db=db,
            case=case_a,
            event_type="REPORT_LINKED",
            payload={"report_id": rpt_a3.public_id, "reason": "Corroborating observation merged: 88% similarity"},
            actor=reviewer_user,
            public_actor_label="Community Reviewer Rajesh Sharma",
        )
        LedgerService.append_event(
            db=db,
            case=case_a,
            event_type="CASE_VERIFIED",
            payload={"status": "VERIFIED", "verified_reports_count": 3},
            actor=reviewer_user,
            public_actor_label="Community Reviewer Rajesh Sharma",
        )

        # -------------------------------------------------------------
        # SCENARIO B — A Claimed Repair is DISPUTED
        # Streetlight claimed resolved by operator, but citizen disputes it
        # -------------------------------------------------------------
        score_b, band_b, breakdown_b = PriorityEngine.calculate_priority(
            category_weight=cat_lighting.default_severity_weight,
            report_count=1,
            created_at=now - timedelta(days=4),
        )
        case_b = Case(
            public_id="CAS-2026-0002",
            category_id=cat_lighting.id,
            service_area_id=service_area.id,
            title="Complete blackout of streetlights on 56 Dukan corridor",
            description="Three consecutive streetlights out along 56 Dukan evening market street, pitch black pedestrian crossing.",
            latitude=22.7231,
            longitude=75.8812,
            address_reference="56 Dukan Street, Chhappan, Indore",
            state=CaseState.DISPUTED,
            priority_score=score_b,
            priority_band=band_b,
            priority_breakdown=breakdown_b,
            created_at=now - timedelta(days=4),
        )
        db.add(case_b)
        db.flush()

        rpt_b = Report(
            public_id="RPT-2026-0004",
            category_id=cat_lighting.id,
            reporter_id=citizen_1.id,
            title="Three streetlights out on 56 Dukan street",
            description="Dark stretch causing safety issues for late night visitors.",
            latitude=22.7231,
            longitude=75.8812,
            case_id=case_b.id,
            created_at=now - timedelta(days=4),
        )
        db.add(rpt_b)
        db.flush()

        claim_b = ResolutionClaim(
            case_id=case_b.id,
            operator_id=operator_lighting.id,
            work_summary="Replaced 3 faulty LED fixtures and tested phase wiring.",
            actions_taken="Inspected sub-station pole 14 to 16, replaced capacitor and lighting drivers.",
            claimed_at=now - timedelta(days=1),
            status="DISPUTED",
        )
        db.add(claim_b)
        db.flush()

        obs_b = VerificationObservation(
            case_id=case_b.id,
            verifier_id=citizen_2.id,
            outcome=VerificationOutcome.STILL_UNRESOLVED,
            notes="Inspected at 8:30 PM tonight: pole #15 remains completely dark and unlit. The issue is only 50% resolved.",
            is_dispute=True,
            submitted_at=now - timedelta(hours=6),
        )
        db.add(obs_b)
        db.flush()

        LedgerService.append_event(
            db=db,
            case=case_b,
            event_type="REPORT_CREATED",
            payload={"report_id": rpt_b.public_id, "title": rpt_b.title},
            actor=citizen_1,
            public_actor_label="Citizen Aarav Mehta",
        )
        LedgerService.append_event(
            db=db,
            case=case_b,
            event_type="RESOLUTION_CLAIMED",
            payload={"summary": claim_b.work_summary, "operator": "Kavita Jain"},
            actor=operator_lighting,
            public_actor_label="Public Works Operator Kavita Jain",
        )
        LedgerService.append_event(
            db=db,
            case=case_b,
            event_type="RESOLUTION_DISPUTED",
            payload={"outcome": "STILL_UNRESOLVED", "dispute_notes": obs_b.notes},
            actor=citizen_2,
            public_actor_label="Citizen Observer Priya Patel",
        )

        # -------------------------------------------------------------
        # SCENARIO C — Independently Verified Resolution
        # Water leak repaired and verified by independent citizen
        # -------------------------------------------------------------
        score_c, band_c, breakdown_c = PriorityEngine.calculate_priority(
            category_weight=cat_water.default_severity_weight,
            report_count=2,
            created_at=now - timedelta(days=5),
        )
        case_c = Case(
            public_id="CAS-2026-0003",
            category_id=cat_water.id,
            service_area_id=service_area.id,
            title="Municipal water mainline burst flooding Palasia Square",
            description="High pressure municipal water pipeline leaking clean water across Old Palasia road, causing waterlogging.",
            latitude=22.7244,
            longitude=75.8899,
            address_reference="Old Palasia Main Road, near Industry House, Indore",
            state=CaseState.RESOLVED,
            priority_score=score_c,
            priority_band=band_c,
            priority_breakdown=breakdown_c,
            created_at=now - timedelta(days=5),
            resolved_at=now - timedelta(days=1),
        )
        db.add(case_c)
        db.flush()

        rpt_c1 = Report(
            public_id="RPT-2026-0005",
            category_id=cat_water.id,
            reporter_id=citizen_2.id,
            title="Drinking water gushing out onto Palasia road",
            description="Potable water pipe broken under tarmac.",
            latitude=22.7244,
            longitude=75.8899,
            case_id=case_c.id,
            created_at=now - timedelta(days=5),
        )
        db.add(rpt_c1)
        db.flush()

        claim_c = ResolutionClaim(
            case_id=case_c.id,
            operator_id=operator_roads.id,
            work_summary="Excavated line, welded new 8-inch cast iron sleeve, backfilled and resurfaced.",
            actions_taken="Water line pressure restored to 4.2 bar, leak fully sealed.",
            claimed_at=now - timedelta(days=2),
            status="VERIFIED",
        )
        db.add(claim_c)
        db.flush()

        obs_c = VerificationObservation(
            case_id=case_c.id,
            verifier_id=citizen_1.id,
            outcome=VerificationOutcome.CONFIRMED_FIXED,
            notes="Walked through Palasia Square this morning. Pipe is dry, new asphalt patch is completely solid.",
            is_dispute=False,
            submitted_at=now - timedelta(days=1),
        )
        db.add(obs_c)
        db.flush()

        LedgerService.append_event(
            db=db,
            case=case_c,
            event_type="REPORT_CREATED",
            payload={"report_id": rpt_c1.public_id},
            actor=citizen_2,
            public_actor_label="Citizen Priya Patel",
        )
        LedgerService.append_event(
            db=db,
            case=case_c,
            event_type="RESOLUTION_CLAIMED",
            payload={"summary": claim_c.work_summary},
            actor=operator_roads,
            public_actor_label="Public Works Operator Anil Verma",
        )
        LedgerService.append_event(
            db=db,
            case=case_c,
            event_type="RESOLUTION_VERIFIED_AND_CLOSED",
            payload={"outcome": "CONFIRMED_FIXED", "notes": obs_c.notes},
            actor=citizen_1,
            public_actor_label="Independent Citizen Aarav Mehta",
        )

        # -------------------------------------------------------------
        # SCENARIO D — Recurrence Tracking
        # Prior repaired pothole in Sarafa Bazar breaks down again 3 weeks later
        # -------------------------------------------------------------
        prior_resolved_case = Case(
            public_id="CAS-2026-0004",
            category_id=cat_pothole.id,
            service_area_id=service_area.id,
            title="Sarafa Bazar entrance road rutting and pothole",
            description="Cold patch asphalt applied in previous maintenance cycle.",
            latitude=22.7175,
            longitude=75.8540,
            address_reference="Sarafa Bazar Gate, Indore",
            state=CaseState.RESOLVED,
            priority_score=3.2,
            priority_band=PriorityBand.MEDIUM,
            created_at=now - timedelta(days=25),
            resolved_at=now - timedelta(days=20),
        )
        db.add(prior_resolved_case)
        db.flush()

        # New active recurring case
        score_d, band_d, breakdown_d = PriorityEngine.calculate_priority(
            category_weight=cat_pothole.default_severity_weight,
            report_count=1,
            created_at=now - timedelta(days=1),
            is_recurring=True,
        )
        current_recurring_case = Case(
            public_id="CAS-2026-0005",
            category_id=cat_pothole.id,
            service_area_id=service_area.id,
            title="Sarafa Bazar entrance asphalt broken again in exact same spot",
            description="The patch repaired 20 days ago has washed away, exposing sub-base stones.",
            latitude=22.7176,
            longitude=75.8541,
            address_reference="Sarafa Bazar Gate, Indore",
            state=CaseState.UNDER_REVIEW,
            priority_score=score_d,
            priority_band=band_d,
            priority_breakdown=breakdown_d,
            created_at=now - timedelta(days=1),
        )
        db.add(current_recurring_case)
        db.flush()

        rpt_d = Report(
            public_id="RPT-2026-0006",
            category_id=cat_pothole.id,
            reporter_id=citizen_1.id,
            title="Pothole returned at Sarafa Gate",
            description="Exact same hole that was supposedly fixed last month has caved in again.",
            latitude=22.7176,
            longitude=75.8541,
            case_id=current_recurring_case.id,
            created_at=now - timedelta(days=1),
        )
        db.add(rpt_d)
        db.flush()

        recurrence = RecurrenceRelationship(
            prior_case_id=prior_resolved_case.id,
            current_case_id=current_recurring_case.id,
            distance_meters=14.2,
            days_since_prior_resolution=19,
            confidence_score=0.91,
            explanation="Identical geographic footprint (14.2m away), recurring category, within 20 days of verified closure.",
            is_reviewer_confirmed=True,
        )
        db.add(recurrence)
        db.flush()

        LedgerService.append_event(
            db=db,
            case=current_recurring_case,
            event_type="RECURRENCE_IDENTIFIED",
            payload={"prior_case_id": prior_resolved_case.public_id, "confidence": 0.91},
            actor=reviewer_user,
            public_actor_label="Community Reviewer Rajesh Sharma",
        )

        # -------------------------------------------------------------
        # SCENARIO E — Explainable Priority (Dangerous Electrical Wire)
        # High intrinsic hazard gets CRITICAL band with transparent breakdown
        # -------------------------------------------------------------
        score_e, band_e, breakdown_e = PriorityEngine.calculate_priority(
            category_weight=cat_electrical.default_severity_weight,
            report_count=2,
            created_at=now - timedelta(days=3),
        )
        case_e = Case(
            public_id="CAS-2026-0006",
            category_id=cat_electrical.id,
            service_area_id=service_area.id,
            title="Dangling high-voltage live wire near Holkar Stadium bus stop",
            description="Transformer conduit snapped; live sparking cable hanging 6 feet above busy pedestrian sidewalk.",
            latitude=22.7247,
            longitude=75.8778,
            address_reference="Race Course Road, opposite Holkar Stadium Gate 2, Indore",
            state=CaseState.ASSIGNED,
            priority_score=score_e,
            priority_band=band_e,
            priority_breakdown=breakdown_e,
            created_at=now - timedelta(days=3),
        )
        db.add(case_e)
        db.flush()

        rpt_e1 = Report(
            public_id="RPT-2026-0007",
            category_id=cat_electrical.id,
            guest_pseudonym="Suraj Rawat (Commuter)",
            title="Exposed sparking wire at Holkar Stadium stop",
            description="Children waiting for school buses right underneath hanging wire.",
            latitude=22.7247,
            longitude=75.8778,
            case_id=case_e.id,
            created_at=now - timedelta(days=3),
        )
        rpt_e2 = Report(
            public_id="RPT-2026-0008",
            category_id=cat_electrical.id,
            reporter_id=citizen_2.id,
            title="Dangerous electric cable hanging low near stadium",
            description="Sparking whenever wind blows. Needs immediate emergency power cutoff.",
            latitude=22.7248,
            longitude=75.8779,
            case_id=case_e.id,
            created_at=now - timedelta(days=2),
        )
        db.add_all([rpt_e1, rpt_e2])
        db.flush()

        LedgerService.append_event(
            db=db,
            case=case_e,
            event_type="REPORT_CREATED",
            payload={"report_id": rpt_e1.public_id, "title": rpt_e1.title},
            actor=None,
            public_actor_label="Citizen Observer",
        )
        LedgerService.append_event(
            db=db,
            case=case_e,
            event_type="PRIORITY_ESCALATED",
            payload={"score": score_e, "band": band_e.value, "reason": "High voltage hazard + multiple independent reports"},
            actor=reviewer_user,
            public_actor_label="Civic Priority Engine",
        )

        db.commit()
        print("Database successfully seeded with 5 connected scenarios and realistic Indore records!")
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
