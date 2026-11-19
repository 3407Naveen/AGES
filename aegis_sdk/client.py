
import httpx


class AegisClient:
    def __init__(
        self,
        application_id: str,
        base_url: str = "http://127.0.0.1:8000"
    ):
        self.application_id = application_id
        self.base_url = base_url.rstrip("/")
        self.http = httpx.Client(timeout=10.0)

    def send_event(
        self,
        trace_id: str,
        event_type: str,
        name: str,
        status: str = "success",
        duration_ms: float = 0,
        input_data=None,
        output_data=None,
        error_message=None
    ):
        payload = {
            "application_id": self.application_id,
            "trace_id": trace_id,
            "event_type": event_type,
            "name": name,
            "status": status,
            "duration_ms": duration_ms,
            "input_data": input_data,
            "output_data": output_data,
            "error_message": error_message
        }

        response = self.http.post(
            f"{self.base_url}/api/v1/events",
            json=payload
        )

        response.raise_for_status()
        return response.json()

    def close(self):
        self.http.close()
