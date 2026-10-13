import math
from datetime import datetime, timezone
from typing import List
from sqlalchemy.orm import Session
from app.models.entities import Case, CaseState, RecurrenceRelationship


def haversine_distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates the great-circle distance in meters between two coordinates."""
    r = 6371000.0  # Earth's radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return r * c


class RecurrenceEngine:
    """
    Deterministic Recurrence Detection Engine.
    Detects recurring defects by evaluating resolved historical cases
    within 50 meters and 60 days in the same category.
    """

    MAX_DISTANCE_METERS: float = 50.0
    MAX_DAYS_WINDOW: int = 60

    @classmethod
    def find_and_record_recurrences(
        cls, db: Session, current_case: Case
    ) -> List[RecurrenceRelationship]:
        """
        Scans resolved cases in the same category and records RecurrenceRelationship
        records when a recurring defect is mathematically confirmed.
        """
        now = datetime.now(timezone.utc)
        resolved_cases = (
            db.query(Case)
            .filter(
                Case.id != current_case.id,
                Case.category_id == current_case.category_id,
                Case.state == CaseState.RESOLVED,
                Case.resolved_at.isnot(None),
            )
            .all()
        )

        detected_recurrences = []
        for prior in resolved_cases:
            dist = haversine_distance_meters(
                current_case.latitude,
                current_case.longitude,
                prior.latitude,
                prior.longitude,
            )
            if dist > cls.MAX_DISTANCE_METERS:
                continue

            resolved_time = (
                prior.resolved_at
                if prior.resolved_at.tzinfo
                else prior.resolved_at.replace(tzinfo=timezone.utc)
            )
            days_since = int((now - resolved_time).total_seconds() / 86400.0)
            if days_since < 0 or days_since > cls.MAX_DAYS_WINDOW:
                continue

            # Check if recurrence relationship already recorded
            existing = (
                db.query(RecurrenceRelationship)
                .filter(
                    RecurrenceRelationship.prior_case_id == prior.id,
                    RecurrenceRelationship.current_case_id == current_case.id,
                )
                .first()
            )
            if existing:
                continue

            spatial_factor = max(0.0, 1.0 - (dist / cls.MAX_DISTANCE_METERS))
            temporal_factor = max(0.0, 1.0 - (days_since / float(cls.MAX_DAYS_WINDOW)))
            confidence = round(0.6 * spatial_factor + 0.4 * temporal_factor, 2)

            explanation = (
                f"Recurrent infrastructure defect detected: Located {int(dist)}m from prior case "
                f"{prior.public_id} (within {int(cls.MAX_DISTANCE_METERS)}m threshold) and resolved "
                f"{days_since} days ago (<{cls.MAX_DAYS_WINDOW}d limit)."
            )

            rel = RecurrenceRelationship(
                prior_case_id=prior.id,
                current_case_id=current_case.id,
                distance_meters=round(dist, 1),
                days_since_prior_resolution=days_since,
                confidence_score=confidence,
                explanation=explanation,
                is_reviewer_confirmed=False,
            )
            db.add(rel)
            detected_recurrences.append(rel)

        if detected_recurrences:
            db.flush()
        return detected_recurrences
