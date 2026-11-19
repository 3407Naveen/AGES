
import time
from typing import Any


FAULT_TYPES = {
    "LLM_TIMEOUT",
    "SERVICE_UNAVAILABLE",
    "RATE_LIMIT",
    "TOOL_FAILURE",
    "ARTIFICIAL_LATENCY",
}


def inject_fault(
    fault_type: str,
    latency_ms: int = 1000,
    message: str | None = None,
) -> dict[str, Any]:
    """
    Simulate controlled failures for reliability testing.
    """

    fault_type = fault_type.upper()

    if fault_type not in FAULT_TYPES:
        return {
            "status": "invalid_fault",
            "message": f"Unsupported fault type: {fault_type}",
            "supported_faults": sorted(FAULT_TYPES),
        }

    if fault_type == "LLM_TIMEOUT":
        return {
            "status": "failure_injected",
            "fault_type": fault_type,
            "error": message or "Simulated LLM request timeout",
            "http_status": None,
        }

    if fault_type == "SERVICE_UNAVAILABLE":
        return {
            "status": "failure_injected",
            "fault_type": fault_type,
            "error": message or "Simulated service unavailable",
            "http_status": 503,
        }

    if fault_type == "RATE_LIMIT":
        return {
            "status": "failure_injected",
            "fault_type": fault_type,
            "error": message or "Simulated rate limit exceeded",
            "http_status": 429,
        }

    if fault_type == "TOOL_FAILURE":
        return {
            "status": "failure_injected",
            "fault_type": fault_type,
            "error": message or "Simulated tool execution failure",
            "http_status": None,
        }

    if fault_type == "ARTIFICIAL_LATENCY":
        if not 0 <= latency_ms <= 10000:
            return {
                "status": "invalid_latency",
                "message": "Latency must be between 0 and 10000 ms",
            }

        time.sleep(latency_ms / 1000)

        return {
            "status": "fault_injected",
            "fault_type": fault_type,
            "latency_ms": latency_ms,
            "message": "Artificial latency successfully applied",
        }
