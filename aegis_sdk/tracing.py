
from time import perf_counter
from uuid import uuid4


class AegisTrace:
    def __init__(self, client, trace_id=None):
        self.client = client
        self.trace_id = trace_id or str(uuid4())
        self.start_time = None
        self.output_data = None

    def __enter__(self):
        self.start_time = perf_counter()

        self.client.send_event(
            trace_id=self.trace_id,
            event_type="agent_start",
            name="Agent execution started",
            status="success",
            input_data={"message": "Agent started"}
        )

        return self

    def record_event(
        self,
        event_type,
        name,
        duration_ms=0,
        input_data=None,
        output_data=None
    ):
        return self.client.send_event(
            trace_id=self.trace_id,
            event_type=event_type,
            name=name,
            status="success",
            duration_ms=duration_ms,
            input_data=input_data,
            output_data=output_data
        )

    def set_output(self, output_data):
        self.output_data = output_data

    def __exit__(self, exc_type, exc_value, traceback):
        elapsed_ms = (
            (perf_counter() - self.start_time) * 1000
        )

        if exc_type is None:
            self.client.send_event(
                trace_id=self.trace_id,
                event_type="agent_end",
                name="Agent execution completed",
                status="success",
                duration_ms=elapsed_ms,
                output_data=self.output_data
            )
        else:
            self.client.send_event(
                trace_id=self.trace_id,
                event_type="agent_end",
                name="Agent execution failed",
                status="error",
                duration_ms=elapsed_ms,
                error_message=str(exc_value)
            )

        return False
