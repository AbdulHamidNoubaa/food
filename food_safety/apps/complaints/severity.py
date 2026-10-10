"""Complaint severity scoring — explicit configurable weights, not AI."""
from __future__ import annotations

from apps.complaints.models import Complaint
from apps.scans.models import SafetyAssessment


def compute_severity(safety_status: str, prohibited_count: int = 0, is_expired: bool = False, prior_reports: int = 0) -> tuple[int, str]:
    score = 0
    if safety_status == SafetyAssessment.ProductStatus.UNSAFE:
        score += 40
    elif safety_status == SafetyAssessment.ProductStatus.WARNING:
        score += 15
    elif safety_status == SafetyAssessment.ProductStatus.UNKNOWN:
        score += 10

    score += min(prohibited_count, 5) * 10
    if is_expired:
        score += 20
    score += min(prior_reports, 5) * 5

    if score >= 71:
        level = Complaint.Severity.CRITICAL
    elif score >= 46:
        level = Complaint.Severity.HIGH
    elif score >= 21:
        level = Complaint.Severity.MEDIUM
    else:
        level = Complaint.Severity.LOW
    return score, level
