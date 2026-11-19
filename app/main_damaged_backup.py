
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

