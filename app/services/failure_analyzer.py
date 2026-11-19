
def analyze_failure(error_message: str | None, event_type: str):
    message = (error_message or "").lower()

    # 1. Detect downstream failures
    downstream_patterns = [
        "stopped because",
        "failed because",
        "due to the previous error",
        "upstream failure",
        "dependency failed",
        "execution aborted"
    ]

    if any(pattern in message for pattern in downstream_patterns):
        return {
            "category": "DOWNSTREAM_FAILURE",
            "severity": "LOW",
            "root_cause": (
                "This event appears to be a consequence "
                "of an earlier failure, rather than the original cause."
            ),
            "recommendation": (
                "Inspect earlier failed events in the same trace "
                "to identify the original root cause."
            )
        }

    # 2. Detect LLM timeout
    if any(word in message for word in [
        "timeout", "timed out", "time limit", "deadline exceeded"
    ]):
        return {
            "category": "LLM_TIMEOUT",
            "severity": "HIGH",
            "root_cause": (
                "The model or service did not respond "
                "within the allowed time."
            ),
            "recommendation": (
                "Increase the request timeout, check model availability, "
                "and implement retry logic with exponential backoff."
            )
        }

    # 3. Detect service unavailability
    if any(word in message for word in [
        "503", "service unavailable", "unavailable",
        "connection refused", "connection error"
    ]):
        return {
            "category": "SERVICE_UNAVAILABLE",
            "severity": "HIGH",
            "root_cause": (
                "The external model or service could not be reached."
            ),
            "recommendation": (
                "Check service health, network connectivity, API status, "
                "and retry with backoff."
            )
        }

    # 4. Detect rate limits
    if any(word in message for word in [
        "429", "rate limit", "too many requests", "quota exceeded"
    ]):
        return {
            "category": "RATE_LIMIT",
            "severity": "MEDIUM",
            "root_cause": (
                "The service rejected the request because a rate "
                "or usage limit was reached."
            ),
            "recommendation": (
                "Reduce request frequency, add exponential backoff, "
                "and check your API quota."
            )
        }

    # 5. Detect authentication errors
    if any(word in message for word in [
        "401", "403", "unauthorized", "forbidden",
        "invalid api key", "authentication"
    ]):
        return {
            "category": "AUTHENTICATION_ERROR",
            "severity": "HIGH",
            "root_cause": (
                "The request was rejected due to authentication "
                "or permission problems."
            ),
            "recommendation": (
                "Verify credentials, token expiry, and service permissions. "
                "Never expose API keys in logs."
            )
        }

    # 6. Detect retrieval failures
    if any(word in message for word in [
        "retrieval failed", "vector database",
        "embedding error", "index not found"
    ]):
        return {
            "category": "RETRIEVAL_FAILURE",
            "severity": "MEDIUM",
            "root_cause": (
                "The retrieval component could not access "
                "or process the knowledge source."
            ),
            "recommendation": (
                "Check the vector database, embedding configuration, "
                "index availability, and retrieval inputs."
            )
        }

    # 7. Detect tool failures
    if event_type == "tool_call":
        return {
            "category": "TOOL_EXECUTION_FAILURE",
            "severity": "HIGH",
            "root_cause": (
                "An agent tool failed while executing its operation."
            ),
            "recommendation": (
                "Inspect tool arguments, permissions, dependencies, "
                "and exception logs."
            )
        }

    # 8. Unknown failures
    return {
        "category": "UNKNOWN_ERROR",
        "severity": "MEDIUM",
        "root_cause": (
            "The failure could not be classified using "
            "the current detection rules."
        ),
        "recommendation": (
            "Inspect the complete event input, output, "
            "and error message to identify the cause."
        )
    }
