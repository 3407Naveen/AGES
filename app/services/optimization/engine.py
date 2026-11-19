
from typing import Any


def generate_optimization_recommendations(
    average_latency_ms: float,
    maximum_latency_ms: float,
    failure_rate_percent: float,
    total_events: int,
    failed_events: int,
) -> dict[str, Any]:
    """Generate recommendations from observed application metrics."""

    recommendations = []

    if total_events == 0:
        return {
            "status": "insufficient_data",
            "recommendation_count": 0,
            "recommendations": [],
            "message": "No event data is available for optimization analysis."
        }

    if average_latency_ms > 2000:
        recommendations.append({
            "category": "LATENCY",
            "priority": "HIGH",
            "finding": "Average event latency is above 2000 ms.",
            "recommendation": (
                "Inspect slow model calls, reduce unnecessary processing, "
                "and consider caching repeated requests."
            ),
            "observed_value": average_latency_ms
        })
    elif average_latency_ms > 1000:
        recommendations.append({
            "category": "LATENCY",
            "priority": "MEDIUM",
            "finding": "Average event latency is elevated.",
            "recommendation": (
                "Profile slow execution steps and optimize expensive "
                "operations."
            ),
            "observed_value": average_latency_ms
        })

    if maximum_latency_ms > 5000:
        recommendations.append({
            "category": "LATENCY_SPIKE",
            "priority": "HIGH",
            "finding": "At least one event has very high latency.",
            "recommendation": (
                "Investigate slow individual events and configure "
                "appropriate timeouts."
            ),
            "observed_value": maximum_latency_ms
        })

    if failure_rate_percent > 10:
        recommendations.append({
            "category": "RELIABILITY",
            "priority": "HIGH",
            "finding": "Application failure rate exceeds 10%.",
            "recommendation": (
                "Review recurring failure categories, implement retry "
                "handling where appropriate, and investigate root causes."
            ),
            "observed_value": failure_rate_percent
        })
    elif failure_rate_percent > 5:
        recommendations.append({
            "category": "RELIABILITY",
            "priority": "MEDIUM",
            "finding": "Application failure rate is above 5%.",
            "recommendation": (
                "Inspect failed traces and address recurring error patterns."
            ),
            "observed_value": failure_rate_percent
        })

    if failed_events > 0:
        recommendations.append({
            "category": "ERROR_ANALYSIS",
            "priority": "MEDIUM",
            "finding": f"{failed_events} failed events were recorded.",
            "recommendation": (
                "Review failed events and their associated incident "
                "diagnostics."
            ),
            "observed_value": failed_events
        })

    if not recommendations:
        recommendations.append({
            "category": "HEALTH",
            "priority": "LOW",
            "finding": "No optimization thresholds were triggered.",
            "recommendation": (
                "Continue monitoring latency and reliability as traffic grows."
            ),
            "observed_value": average_latency_ms
        })

    return {
        "status": "success",
        "recommendation_count": len(recommendations),
        "recommendations": recommendations,
        "analysis_method": "metric_threshold_based",
        "limitation": (
            "Recommendations are rule-based and depend on the supplied "
            "metrics. They do not guarantee performance improvements."
        )
    }
