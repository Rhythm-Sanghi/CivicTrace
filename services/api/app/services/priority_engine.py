from datetime import datetime, timezone
from typing import Tuple
from app.models.entities import PriorityBand
from app.core.security import canonical_json


class PriorityEngine:
    """
    Explainable Civic Priority Scoring Engine.
    Formula:
      Base Category Weight (1.0 - 3.5)
      + Independent Reports Bonus (+0.4 per extra corroborated report, capped at +2.0)
      + Time Unresolved Bonus (+0.2 per 48 hours unresolved, capped at +1.5)
      + Recurrence History Bonus (+0.8 if recurring defect)
      = Raw Civic Priority Score (1.0 to 10.0 scale)

    Bands:
      >= 6.0: CRITICAL
      >= 4.2: HIGH
      >= 2.5: MEDIUM
      < 2.5: LOW
    """

    @classmethod
    def calculate_priority(
        cls,
        category_weight: float,
        report_count: int,
        created_at: datetime,
        is_recurring: bool = False,
    ) -> Tuple[float, PriorityBand, str]:
        # 1. Base category severity
        base_score = float(category_weight)

        # 2. Corroborated reports (independent reports beyond the first)
        corroborated_count = max(0, report_count - 1)
        corroboration_bonus = min(2.0, corroborated_count * 0.4)

        # 3. Unresolved duration
        now = datetime.now(timezone.utc)
        created = created_at if created_at.tzinfo else created_at.replace(tzinfo=timezone.utc)
        elapsed_hours = max(0.0, (now - created).total_seconds() / 3600.0)
        duration_bonus = min(1.5, (elapsed_hours / 48.0) * 0.2)

        # 4. Recurrence bonus
        recurrence_bonus = 0.8 if is_recurring else 0.0

        raw_total = base_score + corroboration_bonus + duration_bonus + recurrence_bonus
        final_score = round(min(10.0, max(1.0, raw_total)), 2)

        # Determine band
        if final_score >= 6.0:
            band = PriorityBand.CRITICAL
        elif final_score >= 4.2:
            band = PriorityBand.HIGH
        elif final_score >= 2.5:
            band = PriorityBand.MEDIUM
        else:
            band = PriorityBand.LOW

        reasons = []
        if base_score >= 3.0:
            reasons.append(
                "High intrinsic hazard category (e.g. exposed electrical or major road collapse)"
            )
        elif base_score >= 2.0:
            reasons.append("Moderate civic safety category")
        else:
            reasons.append("Standard public works category")

        if corroborated_count > 0:
            reasons.append(f"{corroborated_count} independently corroborated citizen report(s)")

        if elapsed_hours >= 72:
            reasons.append(f"Unresolved for {int(elapsed_hours // 24)} days")

        if is_recurring:
            reasons.append("Identified recurrence of previously claimed repair")

        breakdown = {
            "score": final_score,
            "band": band.value,
            "components": {
                "category_base_weight": base_score,
                "corroboration_bonus": round(corroboration_bonus, 2),
                "unresolved_duration_bonus": round(duration_bonus, 2),
                "recurrence_bonus": recurrence_bonus,
            },
            "reasons": reasons,
            "policy_version": "2026.1-deterministic",
        }

        return final_score, band, canonical_json(breakdown)

    @classmethod
    def recalculate_open_case_priorities(cls, db) -> int:
        """
        Recalculates dynamic priority scores for all open cases to reflect
        time elapsed, corroboration updates, and recurrence status.
        """
        from app.models.entities import (
            Case,
            CaseState,
            Report,
            ReportModerationStatus,
            RecurrenceRelationship,
        )

        open_states = [
            CaseState.SUBMITTED,
            CaseState.UNDER_REVIEW,
            CaseState.VERIFIED,
            CaseState.ASSIGNED,
            CaseState.IN_PROGRESS,
            CaseState.REOPENED,
            CaseState.DISPUTED,
            CaseState.AWAITING_VERIFICATION,
        ]
        open_cases = db.query(Case).filter(Case.state.in_(open_states)).all()
        updated_count = 0
        for case in open_cases:
            report_count = (
                db.query(Report)
                .filter(
                    Report.case_id == case.id,
                    Report.moderation_status == ReportModerationStatus.APPROVED,
                )
                .count()
            )
            if report_count == 0:
                report_count = 1

            is_recurring = (
                db.query(RecurrenceRelationship)
                .filter(RecurrenceRelationship.current_case_id == case.id)
                .first()
                is not None
            )

            cat_weight = case.category.default_severity_weight if case.category else 2.0
            new_score, new_band, new_breakdown = cls.calculate_priority(
                category_weight=cat_weight,
                report_count=report_count,
                created_at=case.created_at,
                is_recurring=is_recurring,
            )
            if new_score != case.priority_score or new_band != case.priority_band:
                case.priority_score = new_score
                case.priority_band = new_band
                case.priority_breakdown = new_breakdown
                updated_count += 1

        if updated_count > 0:
            db.commit()
        return updated_count
