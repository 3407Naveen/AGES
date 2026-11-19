
import sys
from pathlib import Path
from uuid import uuid4

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from aegis_sdk.client import AegisClient

APPLICATION_ID = "5c698f49-31a7-4337-ba69-0f7196d7230a"

def run_failure_test():

    client = AegisClient(APPLICATION_ID)
    trace_id = str(uuid4())

    print("\nStarting AEGIS failure simulation...")
    print("Trace ID:", trace_id)

    try:
        client.send_event(
            trace_id=trace_id,
            event_type="agent_start",
            name="Failure Test Agent",
            status="success",
            input_data={"task": "Generate a response"}
        )

        print("Agent started.")

        client.send_event(
            trace_id=trace_id,
            event_type="llm_call",
            name="Simulated LLM Request",
            status="error",
            duration_ms=1200,
            input_data={"prompt": "Explain artificial intelligence"},
            error_message="Simulated model timeout: request exceeded time limit"
        )

        print("Simulated LLM failure recorded.")

        client.send_event(
            trace_id=trace_id,
            event_type="agent_end",
            name="Agent Execution Failed",
            status="error",
            duration_ms=1200,
            error_message="Agent stopped because the LLM request failed."
        )

        print("\nFailure simulation completed.")
        print("Trace ID:", trace_id)

    finally:
        client.close()


if __name__ == "__main__":
    run_failure_test()
