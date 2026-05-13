# app\services\review_session_service.py

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import uuid4

from app.domain.readiness_models import ReadinessScore
from app.domain.recommendation_models import RecommendationTask
from app.domain.review_models import (
    ClaimResolution,
    DocumentWarning,
    ReviewSession,
    ReviewStatus,
    WarningSeverity,
)


class ReviewSessionService:
    """Service for managing human review sessions."""

    def __init__(self) -> None:
        # TODO: Inject repositories
        # self._session_repo = session_repository
        # self._document_repo = document_repository
        # self._evaluation_repo = evaluation_repository
        pass

    def create_review_session(
        self,
        document_id: str,
        user_id: str,
        readiness_score: ReadinessScore,
        recommendations: list[RecommendationTask],
        previous_version_id: Optional[str] = None,
    ) -> ReviewSession:
        """Create a new review session from analysis results."""
        session_id = f"review_{document_id}_{int(datetime.now().timestamp())}"

        # Extract unresolved claims from readiness analysis
        unresolved_claims = self._extract_unresolved_claims(readiness_score)

        # Categorize warnings and failures
        warnings = []
        critical_failures = []

        for warning in readiness_score.warnings:
            doc_warning = DocumentWarning(
                code="readiness_warning",
                message=warning,
                severity="warning",
                section="general",
            )
            warnings.append(doc_warning)

        for blocker in readiness_score.blocking_issues:
            doc_warning = DocumentWarning(
                code="blocking_issue",
                message=blocker,
                severity="critical",
                section="general",
            )
            critical_failures.append(doc_warning)

        # Calculate readiness blockers
        readiness_blockers = readiness_score.blocking_issues.copy()

        # Create version diff (placeholder - would compare with previous version)
        version_diff = self._calculate_version_diff(document_id, previous_version_id)

        session = ReviewSession(
            session_id=session_id,
            document_id=document_id,
            user_id=user_id,
            unresolved_claims=unresolved_claims,
            warnings=warnings,
            critical_failures=critical_failures,
            recommendations=recommendations,
            readiness_score=readiness_score,
            readiness_blockers=readiness_blockers,
            previous_version_id=previous_version_id,
            version_diff=version_diff,
            status="review_required" if self._requires_review(readiness_score, recommendations) else "draft",
        )

        # TODO: Persist session
        # self._session_repo.save_session(session)

        return session

    def update_claim_resolution(
        self,
        session_id: str,
        claim_text: str,
        fact_status: str,
        resolution_reason: Optional[str] = None,
    ) -> ReviewSession:
        """Update the resolution status of a claim in the review session."""
        # TODO: Load session from repository
        # session = self._session_repo.get_session(session_id)

        # For now, create a mock session for demonstration
        session = self._create_mock_session(session_id)

        # Find and update the claim
        for claim in session.unresolved_claims:
            if claim.claim_text == claim_text:
                claim.fact_status = fact_status
                claim.resolved_at = datetime.now()
                claim.resolution_reason = resolution_reason
                break

        session.updated_at = datetime.now()

        # TODO: Persist updated session
        # self._session_repo.save_session(session)

        return session

    def submit_review_decision(
        self,
        session_id: str,
        reviewer_id: str,
        review_decision: dict,  # Would be ReviewDecision object
    ) -> ReviewSession:
        """Submit final review decision for the session."""
        # TODO: Load and update session
        # session = self._session_repo.get_session(session_id)
        # session.review_decision = review_decision
        # session.reviewer_id = reviewer_id
        # session.status = "reviewed"
        # session.updated_at = datetime.now()

        # TODO: Persist updated session

        # For now, return mock
        session = self._create_mock_session(session_id)
        session.status = "reviewed"
        session.reviewer_id = reviewer_id
        session.updated_at = datetime.now()

        return session

    def get_review_session(self, session_id: str) -> Optional[ReviewSession]:
        """Retrieve a review session by ID."""
        # TODO: Load from repository
        # return self._session_repo.get_session(session_id)

        # Mock implementation
        return self._create_mock_session(session_id)

    def _extract_unresolved_claims(self, readiness_score: ReadinessScore) -> list[ClaimResolution]:
        """Extract unresolved claims from readiness analysis."""
        claims = []

        # This would analyze the document content to extract claims
        # For now, create mock claims based on readiness issues

        for issue in readiness_score.blocking_issues + readiness_score.warnings:
            if "evidence" in issue.lower() or "claim" in issue.lower():
                claim = ClaimResolution(
                    claim_text=f"Extracted claim from: {issue}",
                    fact_status="needs_confirmation",
                )
                claims.append(claim)

        return claims

    def _calculate_version_diff(
        self,
        document_id: str,
        previous_version_id: Optional[str],
    ) -> dict:
        """Calculate diff between current and previous document versions."""
        if not previous_version_id:
            return {"type": "new_document", "changes": []}

        # TODO: Implement actual diff calculation
        # This would compare document contents and return structured diff

        return {
            "type": "version_comparison",
            "changes": [
                {"type": "added", "section": "experience", "content": "New achievement added"},
                {"type": "modified", "section": "skills", "content": "Updated skill descriptions"},
            ],
            "previous_version_id": previous_version_id,
        }

    def _requires_review(
        self,
        readiness_score: ReadinessScore,
        recommendations: list[RecommendationTask],
    ) -> bool:
        """Determine if the document requires human review."""
        # Require review if there are blocking issues or critical recommendations
        has_blocking_issues = len(readiness_score.blocking_issues) > 0
        has_critical_recommendations = any(
            task.priority.value == "critical" or task.blocking
            for task in recommendations
        )
        low_readiness = readiness_score.overall_score < 0.6

        return has_blocking_issues or has_critical_recommendations or low_readiness

    def _create_mock_session(self, session_id: str) -> ReviewSession:
        """Create a mock session for testing/demonstration."""
        return ReviewSession(
            session_id=session_id,
            document_id="mock_doc",
            user_id="mock_user",
            unresolved_claims=[
                ClaimResolution(
                    claim_text="Led a team of 5 developers",
                    fact_status="needs_confirmation",
                ),
                ClaimResolution(
                    claim_text="Increased performance by 40%",
                    fact_status="confirmed",
                    resolved_at=datetime.now(),
                ),
            ],
            warnings=[
                DocumentWarning(
                    code="vague_metric",
                    message="Consider adding specific metrics",
                    severity="warning",
                    section="experience",
                ),
            ],
            critical_failures=[],
            recommendations=[],
            readiness_blockers=["Missing key evidence"],
        )