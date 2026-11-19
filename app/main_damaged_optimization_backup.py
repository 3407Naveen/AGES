
@app.get("/api/v1/optimization/recommendations")
def get_optimization_recommendations():
    connection = get_connection()

    try:
        performance = connection.execute(
            """
            SELECT
                COUNT(*) AS total_events,
                COALESCE(AVG(duration_ms), 0)
                    AS average_latency_ms,
                COALESCE(MAX(duration_ms), 0)
                    AS maximum_latency_ms,
                COALESCE(
                    SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END),
                    0
                ) AS failed_events
            FROM events
            """
        ).fetchone()

        total_events = performance["total_events"]
        failed_events = performance["failed_events"]

        trace_stats = connection.execute(
            """
            SELECT
                COUNT(DISTINCT trace_id) AS total_traces,
                COUNT(DISTINCT CASE
                    WHEN status = 'error' THEN trace_id
                END) AS failed_traces
            FROM events
            """
        ).fetchone()

        total_traces = trace_stats["total_traces"]
        failed_traces = trace_stats["failed_traces"]

        failure_rate = (
            failed_traces / total_traces * 100
            if total_traces > 0 else 0
        )

        result = generate_optimization_recommendations(
            average_latency_ms=float(
                performance["average_latency_ms"]
            ),
            maximum_latency_ms=float(
                performance["maximum_latency_ms"]
            ),
            failure_rate_percent=round(failure_rate, 2),
            total_events=total_events,
            failed_events=failed_events,
        )

        return {
            "message": "Optimization analysis completed",
            "application_metrics": {
                "total_traces": total_traces,
                "failed_traces": failed_traces,
                "failure_rate_percent": round(failure_rate, 2),
                "total_events": total_events,
                "failed_events": failed_events,
                "average_latency_ms": round(
                    float(performance["average_latency_ms"]), 2
                ),
                "maximum_latency_ms": round(
                    float(performance["maximum_latency_ms"]), 2
                ),
            },
            "optimization": result,
        }

    finally:
        connection.close()
