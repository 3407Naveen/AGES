
from typing import Any


DEFAULT_THRESHOLDS = {
    "min_evaluation_score": 70.0,
    "max_failure_rate": 5.0,
    "max_latency_ms": 2000.0,
}


def evaluate_release(
    evaluation_score: float,
    failure_rate: float,
    latency_ms: float,
    security_passed: bool,
    regression_passed: bool,
    thresholds: dict[str, float] | None = None,
) -> dict[str, Any]:
    """
    Evaluate whether an AI application is ready for release.
    """

    limits = DEFAULT_THRESHOLDS.copy()

    if thresholds:
        limits.update(thresholds)

    checks = [
        {
            "name": "evaluation_score",
            "passed": evaluation_score >= limits["min_evaluation_score"],
            "actual": evaluation_score,
            "required": f">= {limits['min_evaluation_score']}",
        },
        {
            "name": "failure_rate",
            "passed": failure_rate <= limits["max_failure_rate"],
            "actual": failure_rate,
            "required": f"<= {limits['max_failure_rate']}%",
        },
        {
            "name": "latency",
            "passed": latency_ms <= limits["max_latency_ms"],
            "actual": latency_ms,
            "required": f"<= {limits['max_latency_ms']} ms",
        },
        {
            "name": "security",
            "passed": security_passed,
            "actual": security_passed,
            "required": "Security tests must pass",
        },
        {
            "name": "regression",
            "passed": regression_passed,
            "actual": regression_passed,
            "required": "Regression tests must pass",
        },
    ]

    failed_checks = [
        check["name"]
        for check in checks
        if not check["passed"]
    ]

    approved = len(failed_checks) == 0

    return {
        "release_status": "APPROVED" if approved else "BLOCKED",
        "approved": approved,
        "total_checks": len(checks),
        "passed_checks": len(checks) - len(failed_checks),
        "failed_checks": len(failed_checks),
        "blocking_reasons": failed_checks,
        "checks": checks,
        "thresholds": limits,
    }
