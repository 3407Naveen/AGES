import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from time import perf_counter

from aegis_sdk.client import AegisClient
from aegis_sdk.tracing import AegisTrace


APPLICATION_ID = "5c698f49-31a7-4337-ba69-0f7196d7230a"


def simulated_llm(prompt):
    """A deterministic demo response. No external API is used."""
    return "Artificial intelligence enables machines to perform tasks that normally require human intelligence."


def knowledge_search(query):
    """A simulated knowledge retrieval tool."""
    return [
        "AI enables machines to perform intelligent tasks.",
        "Machine learning is a subset of artificial intelligence.",
        "Deep learning uses neural networks."
    ]


def run_agent():
    client = AegisClient(
        application_id=APPLICATION_ID
    )

    try:
        with AegisTrace(client) as trace:

            user_query = "Explain artificial intelligence"

            # Step 1: Simulated LLM call
            start = perf_counter()
            response = simulated_llm(user_query)
            llm_duration = (perf_counter() - start) * 1000

            trace.record_event(
                event_type="llm_call",
                name="Demo model generation",
                duration_ms=llm_duration,
                input_data={"prompt": user_query},
                output_data={"response": response}
            )

            # Step 2: Simulated tool call
            start = perf_counter()
            results = knowledge_search("artificial intelligence")
            tool_duration = (perf_counter() - start) * 1000

            trace.record_event(
                event_type="tool_call",
                name="Demo knowledge search",
                duration_ms=tool_duration,
                input_data={"query": "artificial intelligence"},
                output_data={"results": results}
            )

            # Step 3: Save final answer
            final_answer = response

            trace.set_output({
                "final_answer": final_answer
            })

            print("\nAgent execution completed!")
            print("Trace ID:", trace.trace_id)
            print("Final answer:", final_answer)

    finally:
        client.close()


if __name__ == "__main__":
    run_agent()
