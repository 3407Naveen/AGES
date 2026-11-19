
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "aegis.db"


def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    connection = get_connection()

    try:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS applications (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                description TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            )
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY,
                application_id TEXT NOT NULL,
                trace_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                name TEXT NOT NULL,
                status TEXT NOT NULL,
                duration_ms REAL,
                input_data TEXT,
                output_data TEXT,
                error_message TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (application_id) REFERENCES applications(id)
            )
        """)

        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_trace
            ON events(trace_id)
        """)

        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_app
            ON events(application_id)
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS incidents (
                incident_id TEXT PRIMARY KEY,
                trace_id TEXT NOT NULL UNIQUE,
                application_id TEXT,
                title TEXT NOT NULL,
                severity TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                root_cause_category TEXT NOT NULL,
                root_cause_event_id TEXT,
                root_cause_event_name TEXT,
                description TEXT NOT NULL,
                recommendation TEXT NOT NULL,
                related_failure_count INTEGER NOT NULL DEFAULT 0,
                resolution_notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (application_id) REFERENCES applications(id)
            )
        """)

        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_incidents_status
            ON incidents(status)
        """)

        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_incidents_severity
            ON incidents(severity)
        """)

        connection.commit()

    finally:
        connection.close()
