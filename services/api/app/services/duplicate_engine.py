import math
import re
from typing import List, Dict, Any
from datetime import timezone
from sqlalchemy.orm import Session
from app.models.entities import Report, Case, DuplicateCandidate, CaseState
from app.core.security import canonical_json

def haversine_distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points in meters using Haversine formula."""
    R = 6371000.0 # Earth's radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c

def tokenize_and_normalize(text: str) -> set:
    """Tokenize text into lowercase alphanumeric words, eliminating basic noise."""
    tokens = re.findall(r"\b[a-zA-Z0-9]{3,}\b", text.lower())
    stop_words = {"the", "and", "near", "front", "road", "street", "issue", "problem", "there", "with"}
    return {t for t in tokens if t not in stop_words}

def jaccard_similarity(set_a: set, set_b: set) -> float:
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a.intersection(set_b))
    union = len(set_a.union(set_b))
    return float(intersection) / float(union) if union > 0 else 0.0


class DuplicateDetectionEngine:
    """
    Deterministic CPU-based duplicate suggestion engine.
    Weights:
      Spatial Proximity: 35%
      Text Similarity: 30%
      Category Compatibility: 20%
      Temporal Proximity: 15%
    """
    MAX_SPATIAL_METERS = 300.0 # Candidates farther than 300m get 0 spatial score
    MAX_TEMPORAL_DAYS = 30.0

    @classmethod
    def evaluate_candidate(cls, report: Report, target_case: Case) -> Dict[str, Any]:
        # 1. Spatial distance
        dist_m = haversine_distance_meters(
            report.latitude, report.longitude, target_case.latitude, target_case.longitude
        )
        if dist_m <= cls.MAX_SPATIAL_METERS:
            # Linear decay from 1.0 at 0m to 0.0 at 300m
            spatial_score = max(0.0, 1.0 - (dist_m / cls.MAX_SPATIAL_METERS))
        else:
            spatial_score = 0.0

        # 2. Category compatibility
        if report.category_id == target_case.category_id:
            category_score = 1.0
        else:
            category_score = 0.0

        # 3. Text similarity (combined title and description)
        tokens_report = tokenize_and_normalize(f"{report.title} {report.description}")
        tokens_case = tokenize_and_normalize(f"{target_case.title} {target_case.description}")
        text_score = jaccard_similarity(tokens_report, tokens_case)

        # 4. Temporal relevance
        # Compare created_at timestamps safely converting to UTC
        report_dt = report.created_at
        if report_dt and report_dt.tzinfo is None:
            report_dt = report_dt.replace(tzinfo=timezone.utc)
        case_dt = target_case.updated_at or target_case.created_at
        if case_dt and case_dt.tzinfo is None:
            case_dt = case_dt.replace(tzinfo=timezone.utc)

        if report_dt and case_dt:
            diff_days = abs((report_dt - case_dt).total_seconds()) / 86400.0
        else:
            diff_days = 0.0

        if diff_days <= cls.MAX_TEMPORAL_DAYS:
            temporal_score = max(0.0, 1.0 - (diff_days / cls.MAX_TEMPORAL_DAYS))
        else:
            temporal_score = 0.1

        # Composite score
        # 35% spatial, 30% text, 20% category, 15% temporal
        composite_score = (
            0.35 * spatial_score +
            0.30 * text_score +
            0.20 * category_score +
            0.15 * temporal_score
        )

        # Rationale bullets
        reasons = []
        if dist_m < 50:
            reasons.append(f"Immediate physical proximity ({dist_m:.1f}m away)")
        elif dist_m <= cls.MAX_SPATIAL_METERS:
            reasons.append(f"Within neighbourhood vicinity ({dist_m:.1f}m away)")
        else:
            reasons.append(f"Substantial geographic distance ({dist_m:.1f}m away)")

        if category_score == 1.0:
            reasons.append("Identical infrastructure category")
        else:
            reasons.append("Different issue category")

        if text_score > 0.4:
            reasons.append(f"High vocabulary overlap in issue description ({text_score*100:.0f}%)")
        elif text_score > 0.15:
            reasons.append(f"Moderate vocabulary overlap in issue description ({text_score*100:.0f}%)")

        if diff_days < 7:
            reasons.append(f"Recent concurrent activity ({diff_days:.1f} days apart)")

        explanation = {
            "summary": f"Similarity score: {composite_score*100:.1f}%",
            "distance_meters": round(dist_m, 1),
            "reasons": reasons,
            "weights": {
                "spatial": 0.35,
                "text": 0.30,
                "category": 0.20,
                "temporal": 0.15,
            },
        }

        return {
            "distance_meters": dist_m,
            "spatial_score": round(spatial_score, 3),
            "text_score": round(text_score, 3),
            "category_score": round(category_score, 3),
            "temporal_score": round(temporal_score, 3),
            "composite_score": round(composite_score, 3),
            "explanation": canonical_json(explanation),
        }

    @classmethod
    def find_and_record_candidates(cls, db: Session, report: Report) -> List[DuplicateCandidate]:
        """
        Scans open and active cases within spatial threshold and generates candidate records.
        """
        # Active case states to check against
        active_states = [
            CaseState.SUBMITTED,
            CaseState.UNDER_REVIEW,
            CaseState.VERIFIED,
            CaseState.ASSIGNED,
            CaseState.IN_PROGRESS,
            CaseState.AWAITING_VERIFICATION,
        ]

        # Bounding box filter approximation (~0.005 degrees latitude is ~550m)
        lat_delta = 0.005
        lon_delta = 0.005

        cases = (
            db.query(Case)
            .filter(
                Case.state.in_(active_states),
                Case.latitude.between(report.latitude - lat_delta, report.latitude + lat_delta),
                Case.longitude.between(report.longitude - lon_delta, report.longitude + lon_delta),
            )
            .all()
        )

        candidates = []
        for c in cases:
            eval_res = cls.evaluate_candidate(report, c)
            # If composite score is >= 0.35, suggest as duplicate candidate
            if eval_res["composite_score"] >= 0.35:
                cand = DuplicateCandidate(
                    report_id=report.id,
                    target_case_id=c.id,
                    distance_meters=eval_res["distance_meters"],
                    spatial_score=eval_res["spatial_score"],
                    text_score=eval_res["text_score"],
                    category_score=eval_res["category_score"],
                    temporal_score=eval_res["temporal_score"],
                    composite_score=eval_res["composite_score"],
                    explanation=eval_res["explanation"],
                    status="PENDING",
                )
                db.add(cand)
                candidates.append(cand)

        db.flush()
        return candidates
