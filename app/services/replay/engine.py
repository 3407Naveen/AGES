
import json
from typing import Any


def normalize_json(value: Any) -> Any:
    """Normalize JSON values for reliable comparison."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value

    if isinstance(value, dict):
        return {
            key: normalize_json(item)
            for key, item in sorted(value.items())
        }

    if isinstance(value, list):
        return [normalize_json(item) for item in value]

    return value


def compare_events(original: dict, replayed: dict) -> dict:
    """Compare a recorded event with its replay representation."""

    differences = []

    fields = [
        "event_type",
        "name",
        "status",
        "input_data",
        "output_data",
        "error_message",
    ]

    for field in fields:
        original_value = normalize_json(original.get(field))
        replayed_value = normalize_json(replayed.get(field))

        if original_value != replayed_value:
            differences.append({
                "field": field,
                "original": original_value,
                "replayed": replayed_value,
            })

    return {
        "event_name": original.get("name"),
        "match": len(differences) == 0,
        "differences": differences,
    }


def replay_trace(events: list[dict]) -> dict:
    """
    Reconstruct a trace from recorded events.

    This version compares stored records. It does not
    execute external LLM or tool calls again.
    """

    if not events:
        return {
            "status": "empty",
            "total_events": 0,
            "successful_events": 0,
            "failed_events": 0,
            "events": [],
        }

    reconstructed = []

    for event in events:
        reconstructed.append({
            "id": event.get("id"),
            "event_type": event.get("event_type"),
            "name": event.get("name"),
            "status": event.get("status"),
            "duration_ms": event.get("duration_ms"),
            "input_data": normalize_json(
                event.get("input_data")
            ),
            "output_data": normalize_json(
                event.get("output_data")
            ),
            "error_message": event.get("error_message"),
            "created_at": event.get("created_at"),
        })

    successful = sum(
        1 for event in reconstructed
        if event.get("status") == "success"
    )

    failed = len(reconstructed) - successful

    return {
        "status": "replay_completed",
        "total_events": len(reconstructed),
        "successful_events": successful,
        "failed_events": failed,
        "events": reconstructed,
    }


def generate_regression_test(trace_id: str, events: list[dict]) -> dict:
    """Convert a recorded trace into a regression test definition."""

    expected_events = []

    for event in events:
        expected_events.append({
            "event_type": event.get("event_type"),
            "name": event.get("name"),
            "expected_status": event.get("status"),
            "expected_input": normalize_json(
                event.get("input_data")
            ),
            "expected_output": normalize_json(
                event.get("output_data")
            ),
            "expected_error": event.get("error_message"),
        })

    return {
        "trace_id": trace_id,
        "test_name": f"Regression test for trace {trace_id}",
        "total_expected_events": len(expected_events),
        "expected_events": expected_events,
    }

def execute_regression_test(
    expected_events: list[dict],
    actual_events: list[dict]
) -> dict:
    """Compare actual events against expected regression specifications."""

    comparisons = []
    total_expected = len(expected_events)
    total_actual = len(actual_events)
    total = max(total_expected, total_actual)

    for index in range(total):
        if index >= total_expected:
            comparisons.append({
                "event_index": index,
                "match": False,
                "reason": "Unexpected extra event"
            })
            continue

        if index >= total_actual:
            comparisons.append({
                "event_index": index,
                "match": False,
                "reason": "Expected event is missing"
            })
            continue

        specification = expected_events[index]

        expected = {
            "event_type": specification.get("event_type"),
            "name": specification.get("name"),
            "status": specification.get("expected_status"),
            "input_data": normalize_json(
                specification.get("expected_input")
            ),
            "output_data": normalize_json(
                specification.get("expected_output")
            ),
            "error_message": specification.get("expected_error")
        }

        actual = actual_events[index]

        comparison = compare_events(expected, actual)
        comparison["event_index"] = index
        comparisons.append(comparison)

    matched = sum(
        1 for item in comparisons if item["match"]
    )

    failed = total - matched
    passed = total_expected > 0 and failed == 0

    return {
        "status": "passed" if passed else "failed",
        "passed": passed,
        "total_expected_events": total_expected,
        "total_actual_events": total_actual,
        "matched_events": matched,
        "failed_events": failed,
        "match_percentage": round(
            matched / total * 100, 2
        ) if total else 0,
        "comparisons": comparisons,
        "limitation": (
            "Compares supplied event data; does not rerun external "
            "agents, LLMs, or tools."
        )
    }

