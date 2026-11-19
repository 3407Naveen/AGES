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
