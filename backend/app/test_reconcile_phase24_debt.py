"""Tests for the Phase 2.4 reconciliation script.

The script is read-only and runs against a *copy* (here an in-memory SQLite
DB). These tests pin its classification logic so the honest resolved/deferred/
blocked categorisation cannot silently regress.
"""

from __future__ import annotations

import json
import sqlite3

from backend.app.scripts import reconcile_phase24_debt as rec


def _make_db(tmp_path, *, hardware_rows, provenance_rows=()):
    """Create a disposable SQLite DB with the minimal schema needed."""
    db = tmp_path / "spectra_copy.db"
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE hardware (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            manufacturer TEXT NOT NULL,
            type TEXT NOT NULL
        );
        CREATE TABLE sources (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL
        );
        CREATE TABLE field_provenance (
            id INTEGER PRIMARY KEY,
            hardware_id INTEGER,
            benchmark_result_id INTEGER,
            table_name TEXT NOT NULL,
            field_name TEXT NOT NULL,
            evidenced_value TEXT,
            evidence_status TEXT NOT NULL,
            confidence TEXT,
            notes TEXT
        );
        """
    )
    for row in hardware_rows:
        conn.execute(
            "INSERT INTO hardware (id, name, manufacturer, type) VALUES (?,?,?,?)",
            (row["id"], row["name"], row["manufacturer"], row["type"]),
        )
    for row in provenance_rows:
        conn.execute(
            "INSERT INTO field_provenance "
            "(id, hardware_id, benchmark_result_id, table_name, field_name, "
            " evidenced_value, evidence_status, confidence, notes) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (
                row["id"],
                row["hardware_id"],
                row.get("benchmark_result_id"),
                row["table_name"],
                row["field_name"],
                row.get("evidenced_value"),
                row["evidence_status"],
                row.get("confidence"),
                row.get("notes"),
            ),
        )
    conn.commit()
    conn.close()
    return db


def test_reports_hardware_with_no_provenance(tmp_path):
    db = _make_db(
        tmp_path,
        hardware_rows=[
            {"id": 1, "name": "AMD Athlon 200GE", "manufacturer": "AMD", "type": "CPU"},
            {"id": 2, "name": "AMD Ryzen 7 PRO 6860Z", "manufacturer": "AMD", "type": "CPU"},
            {"id": 3, "name": "AMD Ryzen 5 5600X", "manufacturer": "AMD", "type": "CPU"},
        ],
        provenance_rows=[
            {
                "id": 1, "hardware_id": 3, "table_name": "cpu_specifications",
                "field_name": "cores", "evidenced_value": "6",
                "evidence_status": "verified", "confidence": "high",
            },
        ],
    )

    report = rec._report(db)

    assert report["counts"]["hardware"] == 3
    unattributed = report["unattributed_hardware"]
    assert unattributed["total"] == 2
    assert [i["id"] for i in unattributed["items"]] == [1, 2]
    assert unattributed["classification"] == "blocked-irresolvable-no-evidence"


def test_reports_low_confidence_as_already_honest(tmp_path):
    db = _make_db(
        tmp_path,
        hardware_rows=[
            {"id": 1, "name": "Intel Core i5-9400F Processor", "manufacturer": "Intel", "type": "CPU"},
        ],
        provenance_rows=[
            {
                "id": 10, "hardware_id": 1, "table_name": "hardware",
                "field_name": "release_date", "evidenced_value": None,
                "evidence_status": "excluded", "confidence": None,
            },
            {
                "id": 11, "hardware_id": 1, "table_name": "hardware",
                "field_name": "architecture", "evidenced_value": None,
                "evidence_status": "excluded", "confidence": "rejected",
            },
        ],
    )

    report = rec._report(db)

    low = report["low_confidence_provenance"]
    assert low["total"] == 2
    assert low["classification"] == "already-honest-excluded-or-unmatched"
    statuses = {i["evidence_status"] for i in low["items"]}
    assert statuses == {"excluded"}


def test_reports_bare_number_names_as_deferred(tmp_path):
    db = _make_db(
        tmp_path,
        hardware_rows=[
            {"id": 499, "name": "980", "manufacturer": "AMD", "type": "CPU"},
            {"id": 561, "name": "6380", "manufacturer": "AMD", "type": "CPU"},
            {"id": 3, "name": "AMD Ryzen 5 5600X", "manufacturer": "AMD", "type": "CPU"},
        ],
    )

    report = rec._report(db)

    bare = report["bare_number_names"]
    assert bare["total"] == 2
    assert [i["id"] for i in bare["items"]] == [499, 561]
    assert bare["classification"] == "deferred-as-intended-product-model-numbers"


def test_output_is_deterministic(tmp_path):
    db = _make_db(
        tmp_path,
        hardware_rows=[
            {"id": 1, "name": "980", "manufacturer": "AMD", "type": "CPU"},
        ],
        provenance_rows=[
            {
                "id": 1, "hardware_id": 1, "table_name": "hardware",
                "field_name": "release_date", "evidenced_value": None,
                "evidence_status": "excluded", "confidence": None,
            },
        ],
    )

    a = json.dumps(rec._report(db), indent=2, sort_keys=True)
    b = json.dumps(rec._report(db), indent=2, sort_keys=True)
    assert a == b
