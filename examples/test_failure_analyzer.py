
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.services.failure_analyzer import analyze_failure


test_cases = [
    {
        "error": "Simulated model timeout: request exceeded time limit",
        "event_type": "llm_call"
    },
    {
        "error": "503 Service Unavailable",
        "event_type": "llm_call"
    },
    {
        "error": "429 Too Many Requests",
        "event_type": "llm_call"
    },
    {
        "error": "Invalid API key - 401 Unauthorized",
        "event_type": "llm_call"
    },
    {
        "error": "Vector database retrieval failed",
        "event_type": "retrieval"
    },
    {
        "error": "Tool execution crashed",
        "event_type": "tool_call"
    }
]


for index, test in enumerate(test_cases, start=1):
    result = analyze_failure(
        test["error"],
        test["event_type"]
    )

    print(f"\nTEST {index}")
    print("Input:", test["error"])
    print("Category:", result["category"])
    print("Severity:", result["severity"])
    print("Root cause:", result["root_cause"])
    print("Recommendation:", result["recommendation"])
    print("-" * 60)
