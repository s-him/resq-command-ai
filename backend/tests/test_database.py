"""SQLite schema, constraint, versioned migration, and transaction tests. Run with: pytest"""

import sqlite3

import pytest
from fastapi.testclient import TestClient

from app import database, migrations, recommendation_repository
from app.main import app
from app.schemas import OperatorDecision


def _create_legacy_database(db_path):
    """Create a pre-upgrade SQLite database WITHOUT CHECK constraints or newer columns."""
    connection = sqlite3.connect(db_path)
    connection.executescript(
        """
        CREATE TABLE incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hazard_type TEXT NOT NULL,
            description TEXT NOT NULL,
            location TEXT NOT NULL,
            reported_at TEXT NOT NULL,
            people_affected INTEGER NOT NULL,
            help_needed TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'open',
            created_at TEXT NOT NULL
        );

        CREATE TABLE resources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            resource_type TEXT NOT NULL,
            name TEXT NOT NULL,
            quantity_available INTEGER NOT NULL,
            location TEXT NOT NULL,
            availability_status TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            items TEXT NOT NULL,
            unavailable_needs TEXT NOT NULL,
            summary TEXT NOT NULL,
            created_at TEXT NOT NULL
        );

        CREATE TABLE action_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id INTEGER NOT NULL,
            recommendation_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            decision TEXT NOT NULL,
            note TEXT,
            created_at TEXT NOT NULL
        );
        """
    )
    return connection


# ---------- Fresh database constraints & indexes ----------


def test_fresh_database_enforces_foreign_keys_and_checks(client):
    connection = database.get_connection()
    try:
        # Foreign key enforced on recommendations
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO recommendations
                    (incident_id, status, items, unavailable_needs, summary, created_at)
                VALUES (9999, 'pending', '[]', '[]', 'Orphan', '2026-11-19T08:00:00+00:00')
                """
            )

        # CHECK constraint on resources.quantity_available >= 0
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO resources
                    (resource_type, name, quantity_available, location, availability_status, created_at)
                VALUES ('supply', 'Water', -5, 'Depot', 'available', '2026-11-19T08:00:00+00:00')
                """
            )

        # CHECK constraint on resources.availability_status
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO resources
                    (resource_type, name, quantity_available, location, availability_status, created_at)
                VALUES ('supply', 'Water', 5, 'Depot', 'invalid_status', '2026-11-19T08:00:00+00:00')
                """
            )

        # CHECK constraint on incidents.people_affected >= 0
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO incidents
                    (hazard_type, description, location, reported_at, people_affected,
                     help_needed, status, created_at)
                VALUES ('flood', 'Bad people count', 'Ward 1', '2026-11-19T08:00:00+00:00',
                        -10, '["water"]', 'open', '2026-11-19T08:00:00+00:00')
                """
            )

        # CHECK constraint on action_history.decision
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                """
                INSERT INTO action_history
                    (incident_id, recommendation_id, action, decision, note, created_at)
                VALUES (1, 1, 'bad', 'maybe', NULL, '2026-11-19T08:00:00+00:00')
                """
            )
    finally:
        connection.close()


def test_indexes_and_schema_migrations_exist_after_init(client):
    connection = database.get_connection()
    try:
        index_names = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'index'"
            ).fetchall()
        }
        applied = migrations.get_applied_versions(connection)
    finally:
        connection.close()

    assert {
        "idx_incidents_status",
        "idx_recommendations_incident_id",
        "idx_action_history_incident_id",
        "idx_action_history_recommendation_id",
        "idx_recommendation_items_recommendation_id",
        "idx_recommendation_items_resource_id",
    }.issubset(index_names)
    assert applied == {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15}


# ---------- Upgrading a pre-upgrade legacy database ----------


def test_upgrade_legacy_database_preserves_records_ids_and_enforces_constraints(temp_database):
    conn = _create_legacy_database(temp_database)
    conn.execute(
        """
        INSERT INTO incidents
            (id, hazard_type, description, location, reported_at, people_affected,
             help_needed, status, created_at)
        VALUES (10, 'flood', 'Legacy flood incident with custom ID.', 'Ward 10',
                '2026-11-18T09:00:00+05:30', 30, '["medical"]', 'open',
                '2026-11-18T03:30:00+00:00')
        """
    )
    conn.execute(
        """
        INSERT INTO resources
            (id, resource_type, name, quantity_available, location, availability_status, created_at)
        VALUES (20, 'ambulance', 'Legacy Ambulance', 4, 'Depot 2', 'available',
                '2026-11-18T03:35:00+00:00')
        """
    )
    conn.execute(
        """
        INSERT INTO recommendations
            (id, incident_id, status, items, unavailable_needs, summary, created_at)
        VALUES (30, 10, 'approved', '[]', '[]', 'Legacy rec', '2026-11-18T03:40:00+00:00')
        """
    )
    conn.execute(
        """
        INSERT INTO action_history
            (id, incident_id, recommendation_id, action, decision, note, created_at)
        VALUES (40, 10, 30, 'recommendation_approved', 'approved', 'Legacy note',
                '2026-11-18T03:45:00+00:00')
        """
    )
    conn.commit()
    conn.close()

    # Starting the app runs migrations and backfills severity on the legacy incident.
    with TestClient(app) as client:
        incident = client.get("/api/incidents/10").json()
        resources = client.get("/api/resources").json()
        rec = client.get("/api/recommendations/30").json()
        history = client.get("/api/incidents/10/history").json()

    # All records and exact IDs are preserved.
    assert incident["id"] == 10
    assert incident["location"] == "Ward 10"
    assert incident["severity"]["score"] == 41  # 18 people + 15 immediate + 8 flood; legacy report is stale
    assert incident["latitude"] is None
    assert incident["vulnerable_groups"] == []

    assert len(resources) == 1 and resources[0]["id"] == 20
    assert rec["id"] == 30 and rec["status"] == "approved"
    assert len(history["action_history"]) == 1
    assert history["action_history"][0]["id"] == 40
    assert history["action_history"][0]["note"] == "Legacy note"

    # Constraints are now enforced on the upgraded database!
    check_conn = database.get_connection()
    try:
        with pytest.raises(sqlite3.IntegrityError):
            check_conn.execute(
                """
                INSERT INTO resources
                    (resource_type, name, quantity_available, location, availability_status, created_at)
                VALUES ('supply', 'Bad', -1, 'Depot', 'available', '2026-11-19T00:00:00+00:00')
                """
            )
        with pytest.raises(sqlite3.IntegrityError):
            check_conn.execute(
                """
                INSERT INTO recommendations
                    (incident_id, status, items, unavailable_needs, summary, created_at)
                VALUES (9999, 'pending', '[]', '[]', 'Orphan', '2026-11-19T00:00:00+00:00')
                """
            )
    finally:
        check_conn.close()


# ---------- Re-running migrations safely (idempotency) ----------


def test_old_rules_version_is_recalculated(client):
    from datetime import datetime, timezone
    from app import incident_repository

    created = client.post(
        "/api/incidents",
        json={
            "hazard_type": "earthquake",
            "description": "Reported earthquake shaking near a school building.",
            "location": "Ward 8",
            "reported_at": datetime.now(timezone.utc).isoformat(),
            "people_affected": 30,
            "help_needed": ["medical"],
            "hazard_magnitude": 6.4,
            "hazard_magnitude_unit": "magnitude",
            "provider_alert_level": "orange",
        },
    )
    assert created.status_code == 201, created.text
    incident_id = created.json()["id"]

    connection = database.get_connection()
    try:
        connection.execute(
            "UPDATE incidents SET severity_rules_version = 'demo-rules-v1', severity_score = 1 WHERE id = ?",
            (incident_id,),
        )
        connection.commit()
    finally:
        connection.close()

    assert incident_repository.fill_missing_severity() == 1
    updated = client.get(f"/api/incidents/{incident_id}").json()
    assert updated["severity"]["rules_version"] == "demo-rules-v4"
    assert updated["severity"]["score"] > 1
    assert updated["severity"]["factors"][3]["points"] == 12


def test_migration_013_creates_safe_manual_dispatch_defaults(client):
    settings = client.get("/api/dispatch/settings")
    assert settings.status_code == 200
    assert settings.json()["mode"] == "manual"
    assert settings.json()["paused"] is False
    assert settings.json()["minimum_severity"] == "High"

    connection = database.get_connection()
    try:
        tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        plan_columns = {
            row["name"] for row in connection.execute(
                "PRAGMA table_info(response_plans)"
            ).fetchall()
        }
        versions = migrations.get_applied_versions(connection)
    finally:
        connection.close()

    assert {"dispatch_settings", "dispatch_deployments", "dispatch_audit_events"}.issubset(tables)
    assert "dispatch_mode" in plan_columns
    assert 13 in versions


def test_migration_012_adds_optional_hazard_signal_columns(client):
    connection = database.get_connection()
    try:
        columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(incidents)").fetchall()
        }
        versions = migrations.get_applied_versions(connection)
    finally:
        connection.close()

    assert {"event_at", "hazard_magnitude", "hazard_magnitude_unit", "provider_alert_level"}.issubset(columns)
    assert {12, 13, 15}.issubset(versions)
    assert "vulnerable_groups" in columns


def test_rerunning_migrations_is_safe_and_idempotent(temp_database):
    first = database.init_database()
    second = database.init_database()

    assert first == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
    assert second == []

    connection = database.get_connection()
    try:
        rows = connection.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()
    finally:
        connection.close()

    assert [row["version"] for row in rows] == [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]


# ---------- Invalid legacy rows halt safely without losing data ----------


def test_invalid_legacy_rows_halt_migration_without_modifying_data(temp_database):
    conn = _create_legacy_database(temp_database)
    conn.execute(
        """
        INSERT INTO incidents
            (id, hazard_type, description, location, reported_at, people_affected,
             help_needed, status, created_at)
        VALUES (7, 'fire', 'Invalid negative people count.', 'Ward 7',
                '2026-11-18T09:00:00+05:30', -5, '["medical"]', 'open',
                '2026-11-18T03:30:00+00:00')
        """
    )
    conn.execute(
        """
        INSERT INTO resources
            (id, resource_type, name, quantity_available, location, availability_status, created_at)
        VALUES (8, 'supply', 'Invalid negative qty', -2, 'Depot', 'available',
                '2026-11-18T03:35:00+00:00')
        """
    )
    conn.commit()
    conn.close()

    with pytest.raises(migrations.DatabaseMigrationError) as exc_info:
        database.init_database()

    message = str(exc_info.value)
    assert "Table 'incidents': rows [7]" in message
    assert "Table 'resources': rows [8]" in message

    # Verify the invalid rows were NOT deleted or silently modified.
    verify = sqlite3.connect(temp_database)
    inc_row = verify.execute("SELECT id, people_affected FROM incidents WHERE id = 7").fetchone()
    res_row = verify.execute("SELECT id, quantity_available FROM resources WHERE id = 8").fetchone()
    verify.close()

    assert inc_row == (7, -5)
    assert res_row == (8, -2)


# ---------- Transaction rollback on multi-table write failure ----------


def test_record_decision_rolls_back_if_history_insert_fails(client):
    incident_id = client.post(
        "/api/incidents",
        json={
            "hazard_type": "flood",
            "description": "Incident for transaction rollback test.",
            "location": "Ward 5",
            "reported_at": "2026-11-19T10:00:00+05:30",
            "people_affected": 20,
            "help_needed": ["medical"],
        },
    ).json()["id"]
    rec_id = client.post(f"/api/incidents/{incident_id}/recommendation").json()["id"]

    # Pass a nonexistent incident_id so UPDATE recommendations succeeds,
    # then INSERT INTO action_history fails on FOREIGN KEY (incident_id).
    with pytest.raises(sqlite3.IntegrityError):
        recommendation_repository.record_decision(
            recommendation_id=rec_id,
            incident_id=99999,
            decision=OperatorDecision.APPROVED,
            note="Should be rolled back",
        )

    # Recommendation must STILL be pending (UPDATE was rolled back), and 0 history rows exist.
    rec = client.get(f"/api/recommendations/{rec_id}").json()
    history = client.get(f"/api/incidents/{incident_id}/history").json()

    assert rec["status"] == "pending"
    assert rec["decision_note"] is None
    assert rec["decided_at"] is None
    assert history["action_history"] == []


# ---------- Normalized recommendation_items & Migration 003 ----------


def test_recommendation_items_enforces_fks_positive_qty_and_uniqueness(client):
    incident_id = client.post(
        "/api/incidents",
        json={
            "hazard_type": "flood",
            "description": "Incident for recommendation_items constraint checks.",
            "location": "Ward 6",
            "reported_at": "2026-11-19T10:00:00+05:30",
            "people_affected": 30,
            "help_needed": ["medical"],
        },
    ).json()["id"]
    resource_id = client.post(
        "/api/resources",
        json={
            "resource_type": "ambulance",
            "name": "Unit B",
            "quantity_available": 2,
            "location": "Depot 1",
            "availability_status": "available",
        },
    ).json()["id"]
    rec_id = client.post(f"/api/incidents/{incident_id}/recommendation").json()["id"]

    conn = database.get_connection()
    try:
        # Invalid recommendation_id FK
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO recommendation_items
                    (recommendation_id, resource_id, recommended_quantity,
                     available_quantity, for_help_needed, explanation)
                VALUES (9999, ?, 1, 2, '["medical"]', 'Bad rec FK')
                """,
                (resource_id,),
            )

        # Invalid resource_id FK
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO recommendation_items
                    (recommendation_id, resource_id, recommended_quantity,
                     available_quantity, for_help_needed, explanation)
                VALUES (?, 9999, 1, 2, '["medical"]', 'Bad resource FK')
                """,
                (rec_id,),
            )

        # Negative or zero recommended_quantity
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO recommendation_items
                    (recommendation_id, resource_id, recommended_quantity,
                     available_quantity, for_help_needed, explanation)
                VALUES (?, ?, -1, 2, '["medical"]', 'Negative qty')
                """,
                (rec_id, resource_id),
            )

        # Duplicate (recommendation_id, resource_id) pair
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO recommendation_items
                    (recommendation_id, resource_id, recommended_quantity,
                     available_quantity, for_help_needed, explanation)
                VALUES (?, ?, 1, 2, '["medical"]', 'Duplicate resource in same rec')
                """,
                (rec_id, resource_id),
            )
    finally:
        conn.close()


def test_migration_003_migrates_multiple_json_items_and_preserves_api_shape(temp_database):
    import json

    conn = _create_legacy_database(temp_database)
    conn.execute(
        """
        INSERT INTO incidents
            (id, hazard_type, description, location, reported_at, people_affected,
             help_needed, status, created_at)
        VALUES (10, 'building_collapse', 'Legacy multi-item incident.', 'Sector 9',
                '2026-11-18T10:00:00+05:30', 120, '["medical", "shelter", "rescue"]', 'open',
                '2026-11-18T04:30:00+00:00')
        """
    )
    conn.execute(
        """
        INSERT INTO resources
            (id, resource_type, name, quantity_available, location, availability_status, created_at)
        VALUES
            (20, 'ambulance', 'Ambulance Alpha', 3, 'Central Depot', 'available', '2026-11-18T04:00:00+00:00'),
            (21, 'shelter', 'Community Hall', 150, 'Ward 12', 'available', '2026-11-18T04:05:00+00:00')
        """
    )

    legacy_items = [
        {
            "resource_id": 20,
            "resource_name": "Ambulance Alpha",
            "resource_type": "ambulance",
            "resource_location": "Central Depot",
            "recommended_quantity": 3,
            "available_quantity": 3,
            "for_help_needed": ["medical"],
            "explanation": "Matched 'ambulance' for medical.",
        },
        {
            "resource_id": 21,
            "resource_name": "Community Hall",
            "resource_type": "shelter",
            "resource_location": "Ward 12",
            "recommended_quantity": 120,
            "available_quantity": 150,
            "for_help_needed": ["shelter"],
            "explanation": "Matched 'shelter' for shelter.",
        },
    ]
    legacy_unavailable = [
        {
            "help_needed": ["rescue"],
            "resource_type": "rescue_team",
            "message": "No available 'rescue_team' resource.",
        }
    ]
    conn.execute(
        """
        INSERT INTO recommendations
            (id, incident_id, status, items, unavailable_needs, summary, created_at)
        VALUES (30, 10, 'pending', ?, ?, 'Legacy multi-item rec', '2026-11-18T05:00:00+00:00')
        """,
        (json.dumps(legacy_items), json.dumps(legacy_unavailable)),
    )
    conn.commit()
    conn.close()

    with TestClient(app) as client:
        rec = client.get("/api/recommendations/30").json()

    # Exact API shape & IDs preserved from relational recommendation_items JOIN resources.
    assert rec["id"] == 30
    assert rec["incident_id"] == 10
    assert len(rec["items"]) == 2
    assert rec["items"][0]["resource_id"] == 20
    assert rec["items"][0]["resource_name"] == "Ambulance Alpha"
    assert rec["items"][0]["recommended_quantity"] == 3
    assert rec["items"][1]["resource_id"] == 21
    assert rec["items"][1]["resource_name"] == "Community Hall"
    assert rec["items"][1]["recommended_quantity"] == 120
    assert len(rec["unavailable_needs"]) == 1
    assert rec["unavailable_needs"][0]["resource_type"] == "rescue_team"

    # Legacy JSON column was NOT silently dropped or altered, and re-running migrations is safe.
    assert database.init_database() == []
    verify = database.get_connection()
    try:
        item_count = verify.execute(
            "SELECT COUNT(*) FROM recommendation_items WHERE recommendation_id = 30"
        ).fetchone()[0]
        raw_legacy = verify.execute(
            "SELECT items FROM recommendations WHERE id = 30"
        ).fetchone()["items"]
    finally:
        verify.close()

    assert item_count == 2
    assert len(json.loads(raw_legacy)) == 2


def test_migration_003_halts_without_data_loss_on_missing_legacy_resource(temp_database):
    import json

    conn = _create_legacy_database(temp_database)
    conn.execute(
        """
        INSERT INTO incidents
            (id, hazard_type, description, location, reported_at, people_affected,
             help_needed, status, created_at)
        VALUES (10, 'flood', 'Incident with dangling legacy resource.', 'Ward 2',
                '2026-11-18T10:00:00+05:30', 25, '["medical"]', 'open',
                '2026-11-18T04:30:00+00:00')
        """
    )
    bad_items = [
        {
            "resource_id": 999,  # does NOT exist in resources!
            "resource_name": "Ghost Ambulance",
            "resource_type": "ambulance",
            "resource_location": "Unknown",
            "recommended_quantity": 1,
            "available_quantity": 1,
            "for_help_needed": ["medical"],
            "explanation": "Points to deleted resource.",
        }
    ]
    conn.execute(
        """
        INSERT INTO recommendations
            (id, incident_id, status, items, unavailable_needs, summary, created_at)
        VALUES (31, 10, 'pending', ?, '[]', 'Broken legacy rec', '2026-11-18T05:00:00+00:00')
        """,
        (json.dumps(bad_items),),
    )
    conn.commit()
    conn.close()

    with pytest.raises(migrations.DatabaseMigrationError) as exc_info:
        database.init_database()

    message = str(exc_info.value)
    assert "Recommendation #31" in message
    assert "resource_id=999" in message

    # Verify legacy JSON data was NOT lost or altered, and version 3 was NOT recorded.
    verify = sqlite3.connect(temp_database)
    row = verify.execute("SELECT items FROM recommendations WHERE id = 31").fetchone()
    applied = [
        r[0] for r in verify.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()
    ]
    verify.close()

    assert json.loads(row[0])[0]["resource_id"] == 999
    assert 3 not in applied
