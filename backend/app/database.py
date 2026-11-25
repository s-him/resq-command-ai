"""
SQLite database helpers.

We use Python's built-in `sqlite3` module, so no extra database software
needs to be installed. All data is stored in a single file
(see DATABASE_PATH in config.py), so it survives server restarts.

Schema creation and safe versioned upgrades live in `app/migrations.py`.
"""

import sqlite3

from app import config, migrations


def get_connection() -> sqlite3.Connection:
    """Open a connection to the SQLite database file with foreign keys enforced."""
    # Read the path at call time so tests can point to a temporary database.
    database_path = config.DATABASE_PATH
    database_path.parent.mkdir(parents=True, exist_ok=True)
    # isolation_level=None gives us explicit transaction control (BEGIN/COMMIT/ROLLBACK).
    connection = sqlite3.connect(database_path, isolation_level=None)
    # Enforce FOREIGN KEY constraints on every connection (SQLite disables them by default).
    connection.execute("PRAGMA foreign_keys = ON")
    # Lets us read rows like dictionaries: row["column_name"]
    connection.row_factory = sqlite3.Row
    return connection


def init_database() -> list[int]:
    """Create or safely upgrade the database schema using versioned migrations.

    Called once when the server starts. Existing valid data is never deleted.
    Returns the list of newly applied migration versions.
    """
    connection = get_connection()
    try:
        return migrations.run_migrations(connection)
    finally:
        connection.close()


def is_database_ok() -> bool:
    """Return True if we can open the database and run a trivial query."""
    try:
        connection = get_connection()
        try:
            connection.execute("SELECT 1")
        finally:
            connection.close()
        return True
    except sqlite3.Error:
        return False
