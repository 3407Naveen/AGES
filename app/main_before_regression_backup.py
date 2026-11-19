
import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.database import get_connection, init_db
from app.services.failure_analyzer import analyze_failure
from app.services.evaluation.engine import evaluate_response
from app.services.replay.engine import (
    replay_trace,
    compare_events,
    generate_regression_test,
)
from app.services.fault_injection.engine import inject_fault
from app.services.security.engine import detect_prompt_injection
from app.services.release_gate.engine import evaluate_release


# APPLICATION LIFESPAN

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


# FASTAPI APPLICATION

app = FastAPI(
    title="AEGIS API",
    description="AI Reliability and Engineering Platform",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# MODELS

class ApplicationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = ""


class EventCreate(BaseModel):
    application_id: str
    trace_id: str
    event_type: Literal[
        "agent_start",
        "llm_call",
        "tool_call",
        "retrieval",
        "agent_end"
    ]
    name: str
    status: Literal["success", "error"] = "success"
    duration_ms: float = 0
    input_data: dict | None = None
    output_data: dict | None = None
    error_message: str | None = None


class IncidentUpdate(BaseModel):
    status: Literal[
        "open",
        "investigating",
        "resolved"
    ] | None = None
    resolution_notes: str | None = None


class EvaluationRequest(BaseModel):
    question: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    context: str = ""


class ReplayComparisonRequest(BaseModel):
    replayed_events: list[dict] = Field(min_length=1)


class FaultInjectionRequest(BaseModel):
    fault_type: Literal[
        "LLM_TIMEOUT",
        "SERVICE_UNAVAILABLE",
        "RATE_LIMIT",
        "TOOL_FAILURE",
        "ARTIFICIAL_LATENCY"
    ]
    latency_ms: int = Field(default=1000, ge=0, le=10000)
    message: str | None = None


class SecurityScanRequest(BaseModel):
    text: str = Field(min_length=1, max_length=20000)

class ReleaseGateRequest(BaseModel):
    evaluation_score: float = Field(ge=0, le=100)
    failure_rate: float = Field(ge=0, le=100)
    latency_ms: float = Field(ge=0)
    security_passed: bool
    regression_passed: bool
    min_evaluation_score: float = Field(default=70, ge=0, le=100)
    max_failure_rate: float = Field(default=5, ge=0, le=100)
    max_latency_ms: float = Field(default=2000, ge=0)


class ReleaseAssessmentRequest(BaseModel):
    application_id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    context: str = ""
    security_text: str = Field(min_length=1, max_length=20000)
    regression_passed: bool



# HEALTH

@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "AEGIS API"
    }


# APPLICATIONS

@app.post("/api/v1/apps")
def create_application(data: ApplicationCreate):
    connection = get_connection()

    try:
        existing = connection.execute(
            "SELECT id FROM applications WHERE name = ?",
            (data.name,)
        ).fetchone()

        if existing:
            raise HTTPException(
                status_code=409,
                detail="Application name already exists"
            )

        application_id = str(uuid4())
        created_at = datetime.now(timezone.utc).isoformat()

        connection.execute(
            """
            INSERT INTO applications
            (id, name, description, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                application_id,
                data.name,
                data.description,
                created_at
            )
        )

        connection.commit()

        return {
            "id": application_id,
            "name": data.name,
            "description": data.description,
            "created_at": created_at
        }

    finally:
        connection.close()


@app.get("/api/v1/apps")
def list_applications():
    connection = get_connection()

    try:
        rows = connection.execute(
            "SELECT * FROM applications ORDER BY created_at DESC"
        ).fetchall()

        return {
            "applications": [dict(row) for row in rows]
        }

    finally:
        connection.close()


# EVENT INGESTION

@app.post("/api/v1/events")
def create_event(data: EventCreate):
    connection = get_connection()

    try:
        application = connection.execute(
            "SELECT id FROM applications WHERE id = ?",
            (data.application_id,)
        ).fetchone()

        if not application:
            raise HTTPException(
                status_code=404,
                detail="Application not found"
            )

        event_id = str(uuid4())
        created_at = datetime.now(timezone.utc).isoformat()

        connection.execute(
            """
            INSERT INTO events (
                id, application_id, trace_id, event_type, name,
                status, duration_ms, input_data, output_data,
                error_message, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event_id,
                data.application_id,
                data.trace_id,
                data.event_type,
                data.name,
                data.status,
                data.duration_ms,
                json.dumps(data.input_data)
                if data.input_data is not None else None,
                json.dumps(data.output_data)
                if data.output_data is not None else None,
                data.error_message,
                created_at
            )
        )

        connection.commit()

        return {
            "id": event_id,
            "trace_id": data.trace_id,
            "status": "recorded",
            "created_at": created_at
        }

    finally:
        connection.close()


# TRACE EXPLORER

@app.get("/api/v1/traces")
def list_traces(limit: int = 50):
    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=400,
            detail="Limit must be between 1 and 100"
        )

    connection = get_connection()

    try:
        rows = connection.execute(
            """
            SELECT
                e.trace_id,
                a.name AS application_name,
                COUNT(*) AS event_count,
                SUM(
                    CASE WHEN e.status = 'error'
                    THEN 1 ELSE 0 END
                ) AS failed_events,
                SUM(
                    COALESCE(e.duration_ms, 0)
                ) AS total_duration_ms,
                MAX(e.created_at) AS last_event_at
            FROM events e
            JOIN applications a ON a.id = e.application_id
            GROUP BY e.trace_id, a.name
            ORDER BY last_event_at DESC
            LIMIT ?
            """,
            (limit,)
        ).fetchall()

        traces = []

        for row in rows:
            item = dict(row)
            item["status"] = (
                "failed"
                if item["failed_events"] > 0
                else "success"
            )
            traces.append(item)

        return {
            "total": len(traces),
            "traces": traces
        }

    finally:
        connection.close()


@app.get("/api/v1/traces/{trace_id}")
def get_trace(trace_id: str):
    connection = get_connection()

    try:
        rows = connection.execute(
            """
            SELECT *
            FROM events
            WHERE trace_id = ?
            ORDER BY created_at ASC
            """,
            (trace_id,)
        ).fetchall()

        if not rows:
            raise HTTPException(
                status_code=404,
                detail="Trace not found"
            )

        events = []

        for row in rows:
            event = dict(row)

            for field in ("input_data", "output_data"):
                if event[field]:
                    try:
                        event[field] = json.loads(event[field])
                    except (json.JSONDecodeError, TypeError):
                        pass

            events.append(event)

        return {
            "trace_id": trace_id,
            "event_count": len(events),
            "events": events
        }

    finally:
        connection.close()


# TRACE REPLAY

@app.post("/api/v1/traces/{trace_id}/replay")
def replay_existing_trace(trace_id: str):
    connection = get_connection()

    try:
        rows = connection.execute(
            """
            SELECT *
            FROM events
            WHERE trace_id = ?
            ORDER BY created_at ASC
            """,
            (trace_id,)
        ).fetchall()

        if not rows:
            raise HTTPException(
                status_code=404,
                detail="Trace not found"
            )

        events = []

        for row in rows:
            event = dict(row)

            for field in ("input_data", "output_data"):
                if event[field]:
                    try:
                        event[field] = json.loads(event[field])
                    except (json.JSONDecodeError, TypeError):
                        pass

            events.append(event)

        result = replay_trace(events)

        return {
            "trace_id": trace_id,
            **result,
            "replay_type": "recorded_event_reconstruction",
            "limitations": [
                "This replay reconstructs stored events.",
                "External LLM and tool calls are not executed again."
            ]
        }

    finally:
        connection.close()


# TRACE REPLAY COMPARISON

@app.post("/api/v1/traces/{trace_id}/compare")
def compare_trace_replay(
    trace_id: str,
    data: ReplayComparisonRequest
):
    connection = get_connection()

    try:
        rows = connection.execute(
            """
            SELECT *
            FROM events
            WHERE trace_id = ?
            ORDER BY created_at ASC
            """,
            (trace_id,)
        ).fetchall()

        if not rows:
            raise HTTPException(
                status_code=404,
                detail="Original trace not found"
            )

        original_events = []

        for row in rows:
            event = dict(row)

            for field in ("input_data", "output_data"):
                if event[field]:
                    try:
                        event[field] = json.loads(event[field])
                    except (json.JSONDecodeError, TypeError):
                        pass

            original_events.append(event)

        replayed_events = data.replayed_events

        comparisons = []
        total = max(
            len(original_events),
            len(replayed_events)
        )

        for index in range(total):
            if index >= len(original_events):
                comparisons.append({
                    "event_index": index,
                    "match": False,
                    "reason": "Extra replayed event"
                })
                continue

            if index >= len(replayed_events):
                comparisons.append({
                    "event_index": index,
                    "match": False,
                    "reason": "Missing replayed event"
                })
                continue

            comparison = compare_events(
                original_events[index],
                replayed_events[index]
            )

            comparison["event_index"] = index
            comparisons.append(comparison)

        matching = sum(
            1 for item in comparisons
            if item["match"]
        )

        return {
            "trace_id": trace_id,
            "comparison_status": (
                "identical"
                if matching == total
                else "differences_detected"
            ),
            "total_events_compared": total,
            "matching_events": matching,
            "different_events": total - matching,
            "match_percentage": round(
                matching / total * 100, 2
            ) if total else 100,
            "comparisons": comparisons
        }

    finally:
        connection.close()


# REGRESSION TEST GENERATION

@app.post("/api/v1/traces/{trace_id}/regression-test")
def create_trace_regression_test(trace_id: str):
    connection = get_connection()

    try:
        rows = connection.execute(
            """
            SELECT *
            FROM events
            WHERE trace_id = ?
            ORDER BY created_at ASC
            """,
            (trace_id,)
        ).fetchall()

        if not rows:
            raise HTTPException(
                status_code=404,
                detail="Trace not found"
            )

        events = []

        for row in rows:
            event = dict(row)

            for field in ("input_data", "output_data"):
                if event[field]:
                    try:
                        event[field] = json.loads(event[field])
                    except (json.JSONDecodeError, TypeError):
                        pass

            events.append(event)

        regression_test = generate_regression_test(
            trace_id,
            events
        )

        return {
            "status": "regression_test_generated",
            "regression_test": regression_test
        }

    finally:
        connection.close()


# FAULT INJECTION ENGINE

@app.post("/api/v1/fault-injection")
def create_fault_injection(data: FaultInjectionRequest):
    try:
        result = inject_fault(
            fault_type=data.fault_type,
            latency_ms=data.latency_ms,
            message=data.message
        )

        return {
            "status": "fault_injection_completed",
            "result": result
        }

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Fault injection failed: {str(error)}"
        )


# SECURITY TESTING

@app.post("/api/v1/security/scan")
def scan_prompt_security(data: SecurityScanRequest):
    try:
        result = detect_prompt_injection(data.text)
        return {
            "status": "security_scan_completed",
            "scan": result
        }
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Security scan failed: {str(error)}"
        )




# RELEASE GATE ENGINE

@app.post("/api/v1/release-gate")
def check_release_gate(data: ReleaseGateRequest):
    try:
        thresholds = {
            "min_evaluation_score": data.min_evaluation_score,
            "max_failure_rate": data.max_failure_rate,
            "max_latency_ms": data.max_latency_ms,
        }

        result = evaluate_release(
            evaluation_score=data.evaluation_score,
            failure_rate=data.failure_rate,
            latency_ms=data.latency_ms,
            security_passed=data.security_passed,
            regression_passed=data.regression_passed,
            thresholds=thresholds,
        )

        return {
            "status": "release_gate_evaluated",
            "result": result,
        }

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Release gate evaluation failed: {str(error)}"
        )


# INTEGRATED RELEASE ASSESSMENT

@app.post("/api/v1/release-assessment")
def integrated_release_assessment(data: ReleaseAssessmentRequest):
    connection = get_connection()

    try:
        application = connection.execute(
            "SELECT id, name FROM applications WHERE id = ?",
            (data.application_id,)
        ).fetchone()

        if not application:
            raise HTTPException(
                status_code=404,
                detail="Application not found"
            )

        # Calculate reliability per trace, matching detailed analytics.
        metrics = connection.execute(
            """
            SELECT
                COUNT(*) AS total_traces,
                SUM(CASE WHEN failed_events > 0 THEN 1 ELSE 0 END)
                    AS failed_traces,
                SUM(event_count) AS total_events,
                SUM(failed_events) AS failed_events,
                (
                    SELECT AVG(duration_ms)
                    FROM events
                    WHERE application_id = ?
                ) AS average_latency_ms
            FROM (
                SELECT
                    trace_id,
                    COUNT(*) AS event_count,
                    SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END)
                        AS failed_events
                FROM events
                WHERE application_id = ?
                GROUP BY trace_id
            ) AS trace_metrics
            """,
            (data.application_id, data.application_id)
        ).fetchone()

        total_traces = metrics["total_traces"] or 0
        if total_traces == 0:
            raise HTTPException(
                status_code=422,
                detail="Cannot assess release: this application has no recorded traces"
            )

        failed_traces = metrics["failed_traces"] or 0
        total_events = metrics["total_events"] or 0
        failed_events = metrics["failed_events"] or 0

        failure_rate = round(
            failed_traces / total_traces * 100, 2
        )
        average_latency = round(
            metrics["average_latency_ms"] or 0.0, 2
        )

        evaluation = evaluate_response(
            question=data.question,
            answer=data.answer,
            context=data.context
        )
        evaluation_score = evaluation["overall_score"]

        security_result = detect_prompt_injection(data.security_text)
        security_passed = not security_result.get("is_suspicious", False)

        release_result = evaluate_release(
            evaluation_score=evaluation_score,
            failure_rate=failure_rate,
            latency_ms=average_latency,
            security_passed=security_passed,
            regression_passed=data.regression_passed
        )

        return {
            "status": "release_assessment_completed",
            "application": {
                "id": application["id"],
                "name": application["name"]
            },
            "assessment": {
                "evaluation": {
                    **evaluation,
                    "method": "local_heuristic",
                    "limitation": "This score is heuristic and is not a factuality or hallucination guarantee."
                },
                "security": {
                    **security_result,
                    "method": "regex_based_prompt_injection_checks",
                    "limitation": "This lightweight detector does not identify every possible prompt injection."
                },
                "application_metrics": {
                    "total_traces": total_traces,
                    "failed_traces": failed_traces,
                    "failure_rate_percent": failure_rate,
                    "total_events": total_events,
                    "failed_events": failed_events,
                    "average_event_latency_ms": average_latency,
                    "failure_rate_basis": "failed_traces / total_traces"
                },
                "regression": {
                    "passed": data.regression_passed,
                    "source": "user_supplied_test_result",
                    "limitation": "The API records the supplied result; it does not execute regression tests."
                }
            },
            "release_decision": release_result
        }

    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Release assessment failed: {str(error)}"
        )
    finally:
        connection.close()


# FAILURE INTELLIGENCE AND INCIDENT PERSISTENCE

@app.get("/api/v1/traces/{trace_id}/analysis")
def analyze_trace(trace_id: str):
    connection = get_connection()

    try:
        rows = connection.execute(
            """
            SELECT
                id, application_id, trace_id, event_type, name,
                status, duration_ms, error_message, created_at
            FROM events
            WHERE trace_id = ?
            ORDER BY created_at ASC
            """,
            (trace_id,)
        ).fetchall()

        if not rows:
            raise HTTPException(
                status_code=404,
                detail="Trace not found"
            )

        events = [dict(row) for row in rows]

        failed_events = [
            event for event in events
            if event["status"] == "error"
        ]

        if not failed_events:
            return {
                "trace_id": trace_id,
                "status": "healthy",
                "total_events": len(events),
                "failed_events": 0,
                "incident_count": 0,
                "incidents": []
            }

        diagnoses = []

        for event in failed_events:
            diagnosis = analyze_failure(
                error_message=event["error_message"],
                event_type=event["event_type"]
            )

            diagnoses.append({
                "event_id": event["id"],
                "event_name": event["name"],
                "event_type": event["event_type"],
                "error_message": event["error_message"],
                "duration_ms": event["duration_ms"],
                "analysis": diagnosis
            })

        root_cause = next(
            (
                item for item in diagnoses
                if item["analysis"]["category"]
                != "DOWNSTREAM_FAILURE"
            ),
            diagnoses[0]
        )

        root_cause["failure_role"] = "root_cause"

        related_failures = []

        for item in diagnoses:
            if item is root_cause:
                continue

            item["failure_role"] = "downstream"
            related_failures.append(item)

        severity_order = {
            "HIGH": 3,
            "MEDIUM": 2,
            "LOW": 1
        }

        overall_severity = max(
            (
                item["analysis"]["severity"]
                for item in diagnoses
            ),
            key=lambda severity: severity_order.get(
                severity, 0
            ),
            default="LOW"
        )

        root_analysis = root_cause["analysis"]

        incident_id = f"INC-{trace_id[:8].upper()}"
        title = root_analysis["category"].replace("_", " ")
        application_id = events[0]["application_id"]
        description = root_analysis["root_cause"]
        recommendation = root_analysis["recommendation"]
        now = datetime.now(timezone.utc).isoformat()

        connection.execute(
            """
            INSERT INTO incidents (
                incident_id, trace_id, application_id, title,
                severity, status, root_cause_category,
                root_cause_event_id, root_cause_event_name,
                description, recommendation, related_failure_count,
                resolution_notes, created_at, updated_at
            )
            VALUES (
                ?, ?, ?, ?, ?, 'open', ?, ?, ?, ?, ?, ?, '', ?, ?
            )
            ON CONFLICT(trace_id) DO UPDATE SET
                application_id = excluded.application_id,
                title = excluded.title,
                severity = excluded.severity,
                root_cause_category = excluded.root_cause_category,
                root_cause_event_id = excluded.root_cause_event_id,
                root_cause_event_name = excluded.root_cause_event_name,
                description = excluded.description,
                recommendation = excluded.recommendation,
                related_failure_count = excluded.related_failure_count,
                updated_at = excluded.updated_at
            """,
            (
                incident_id,
                trace_id,
                application_id,
                title,
                overall_severity,
                root_analysis["category"],
                root_cause["event_id"],
                root_cause["event_name"],
                description,
                recommendation,
                len(related_failures),
                now,
                now
            )
        )

        connection.commit()

        saved_incident = connection.execute(
            "SELECT * FROM incidents WHERE trace_id = ?",
            (trace_id,)
        ).fetchone()

        incident = {
            "incident_id": saved_incident["incident_id"],
            "title": saved_incident["title"],
            "severity": saved_incident["severity"],
            "status": saved_incident["status"],
            "root_cause": {
                "event_id": root_cause["event_id"],
                "event_name": root_cause["event_name"],
                "category": root_analysis["category"],
                "severity": root_analysis["severity"],
                "description": description,
                "recommendation": recommendation
            },
            "related_failure_count": len(related_failures),
            "related_failures": related_failures
        }

        return {
            "trace_id": trace_id,
            "status": "failure_detected",
            "total_events": len(events),
            "failed_events": len(failed_events),
            "incident_count": 1,
            "overall_severity": overall_severity,
            "incidents": [incident]
        }

    finally:
        connection.close()


# APPLICATION EVENT HISTORY

@app.get("/api/v1/apps/{application_id}/events")
def get_application_events(application_id: str):
    connection = get_connection()

    try:
        rows = connection.execute(
            """
            SELECT *
            FROM events
            WHERE application_id = ?
            ORDER BY created_at DESC
            """,
            (application_id,)
        ).fetchall()

        return {
            "application_id": application_id,
            "total": len(rows),
            "events": [dict(row) for row in rows]
        }

    finally:
        connection.close()


# ANALYTICS OVERVIEW

@app.get("/api/v1/analytics/overview")
def analytics_overview():
    connection = get_connection()

    try:
        app_count = connection.execute(
            "SELECT COUNT(*) FROM applications"
        ).fetchone()[0]

        trace_count = connection.execute(
            "SELECT COUNT(DISTINCT trace_id) FROM events"
        ).fetchone()[0]

        event_stats = connection.execute(
            """
            SELECT
                COUNT(*) AS total_events,
                SUM(
                    CASE WHEN status = 'success'
                    THEN 1 ELSE 0 END
                ) AS successful_events,
                SUM(
                    CASE WHEN status = 'error'
                    THEN 1 ELSE 0 END
                ) AS failed_events,
                AVG(duration_ms) AS avg_duration_ms
            FROM events
            """
        ).fetchone()

        total = event_stats["total_events"] or 0
        successful = event_stats["successful_events"] or 0
        failed = event_stats["failed_events"] or 0

        success_rate = (
            round(successful / total * 100, 2)
            if total else 0
        )

        grouped_rows = connection.execute(
            """
            SELECT
                event_type,
                COUNT(*) AS count
            FROM events
            GROUP BY event_type
            ORDER BY count DESC
            """
        ).fetchall()

        return {
            "total_applications": app_count,
            "total_traces": trace_count,
            "total_events": total,
            "successful_events": successful,
            "failed_events": failed,
            "success_rate": success_rate,
            "average_duration_ms": round(
                event_stats["avg_duration_ms"] or 0,
                2
            ),
            "event_distribution": [
                dict(row) for row in grouped_rows
            ]
        }

    finally:
        connection.close()


# DETAILED ANALYTICS

@app.get("/api/v1/analytics/detailed")
def detailed_analytics():
    connection = get_connection()

    try:
        failure_categories = connection.execute(
            """
            SELECT
                root_cause_category AS category,
                COUNT(*) AS count
            FROM incidents
            GROUP BY root_cause_category
            ORDER BY count DESC
            """
        ).fetchall()

        application_reliability = connection.execute(
            """
            SELECT
                a.id AS application_id,
                a.name AS application_name,
                COUNT(t.trace_id) AS total_traces,
                SUM(
                    CASE WHEN t.failed_events = 0
                    THEN 1 ELSE 0 END
                ) AS successful_traces,
                SUM(
                    CASE WHEN t.failed_events > 0
                    THEN 1 ELSE 0 END
                ) AS failed_traces
            FROM applications a
            LEFT JOIN (
                SELECT
                    application_id,
                    trace_id,
                    SUM(
                        CASE WHEN status = 'error'
                        THEN 1 ELSE 0 END
                    ) AS failed_events
                FROM events
                GROUP BY application_id, trace_id
            ) t ON a.id = t.application_id
            GROUP BY a.id, a.name
            ORDER BY total_traces DESC
            """
        ).fetchall()

        reliability = []

        for row in application_reliability:
            item = dict(row)

            total = item["total_traces"] or 0
            successful = item["successful_traces"] or 0

            item["failed_traces"] = (
                item["failed_traces"] or 0
            )
            item["successful_traces"] = successful

            item["success_rate"] = (
                round(successful / total * 100, 2)
                if total else 0
            )

            reliability.append(item)

        daily_incidents = connection.execute(
            """
            SELECT
                DATE(created_at) AS date,
                COUNT(*) AS total_incidents,
                SUM(
                    CASE WHEN severity = 'HIGH'
                    THEN 1 ELSE 0 END
                ) AS high,
                SUM(
                    CASE WHEN severity = 'MEDIUM'
                    THEN 1 ELSE 0 END
                ) AS medium,
                SUM(
                    CASE WHEN severity = 'LOW'
                    THEN 1 ELSE 0 END
                ) AS low
            FROM incidents
            WHERE DATE(created_at) >= DATE('now', '-6 days')
            GROUP BY DATE(created_at)
            ORDER BY date ASC
            """
        ).fetchall()

        severity_distribution = connection.execute(
            """
            SELECT
                severity,
                COUNT(*) AS count
            FROM incidents
            GROUP BY severity
            ORDER BY count DESC
            """
        ).fetchall()

        recurring_root_causes = connection.execute(
            """
            SELECT
                root_cause_category AS category,
                COUNT(*) AS occurrences
            FROM incidents
            GROUP BY root_cause_category
            ORDER BY occurrences DESC
            LIMIT 5
            """
        ).fetchall()

        performance = connection.execute(
            """
            SELECT
                COUNT(*) AS total_events,
                ROUND(AVG(duration_ms), 2)
                    AS average_duration_ms,
                ROUND(MAX(duration_ms), 2)
                    AS maximum_duration_ms,
                ROUND(MIN(duration_ms), 2)
                    AS minimum_duration_ms
            FROM events
            """
        ).fetchone()

        return {
            "analytics_status": "success",
            "failure_categories": [
                dict(row) for row in failure_categories
            ],
            "application_reliability": reliability,
            "daily_incident_trends": [
                dict(row) for row in daily_incidents
            ],
            "severity_distribution": [
                dict(row) for row in severity_distribution
            ],
            "recurring_root_causes": [
                dict(row) for row in recurring_root_causes
            ],
            "execution_performance": dict(performance)
        }

    finally:
        connection.close()


# AI EVALUATION ENGINE

@app.post("/api/v1/evaluations")
def create_evaluation(data: EvaluationRequest):
    try:
        result = evaluate_response(
            question=data.question,
            answer=data.answer,
            context=data.context
        )

        return {
            "status": "evaluation_completed",
            "evaluation": result
        }

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Evaluation failed: {str(error)}"
        )


# INCIDENT MANAGEMENT

@app.get("/api/v1/incidents")
def list_incidents(
    status: Literal[
        "open",
        "investigating",
        "resolved"
    ] | None = None,
    severity: Literal[
        "HIGH",
        "MEDIUM",
        "LOW"
    ] | None = None,
    limit: int = 50
):
    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=400,
            detail="Limit must be between 1 and 100"
        )

    connection = get_connection()

    try:
        query = "SELECT * FROM incidents WHERE 1=1"
        parameters = []

        if status:
            query += " AND status = ?"
            parameters.append(status)

        if severity:
            query += " AND severity = ?"
            parameters.append(severity)

        query += " ORDER BY created_at DESC LIMIT ?"
        parameters.append(limit)

        rows = connection.execute(
            query,
            parameters
        ).fetchall()

        return {
            "total": len(rows),
            "incidents": [dict(row) for row in rows]
        }

    finally:
        connection.close()


@app.get("/api/v1/incidents/{incident_id}")
def get_incident(incident_id: str):
    connection = get_connection()

    try:
        row = connection.execute(
            "SELECT * FROM incidents WHERE incident_id = ?",
            (incident_id,)
        ).fetchone()

        if not row:
            raise HTTPException(
                status_code=404,
                detail="Incident not found"
            )

        return dict(row)

    finally:
        connection.close()


@app.patch("/api/v1/incidents/{incident_id}")
def update_incident(
    incident_id: str,
    data: IncidentUpdate
):
    if (
        data.status is None
        and data.resolution_notes is None
    ):
        raise HTTPException(
            status_code=400,
            detail="Provide a status or resolution_notes update"
        )

    connection = get_connection()

    try:
        existing = connection.execute(
            "SELECT * FROM incidents WHERE incident_id = ?",
            (incident_id,)
        ).fetchone()

        if not existing:
            raise HTTPException(
                status_code=404,
                detail="Incident not found"
            )

        new_status = (
            data.status
            if data.status is not None
            else existing["status"]
        )

        new_notes = (
            data.resolution_notes
            if data.resolution_notes is not None
            else existing["resolution_notes"]
        )

        updated_at = datetime.now(timezone.utc).isoformat()

        connection.execute(
            """
            UPDATE incidents
            SET
                status = ?,
                resolution_notes = ?,
                updated_at = ?
            WHERE incident_id = ?
            """,
            (
                new_status,
                new_notes,
                updated_at,
                incident_id
            )
        )

        connection.commit()

        updated = connection.execute(
            "SELECT * FROM incidents WHERE incident_id = ?",
            (incident_id,)
        ).fetchone()

        return {
            "message": "Incident updated successfully",
            "incident": dict(updated)
        }

    finally:
        connection.close()
