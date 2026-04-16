import sqlite3
import os
import logging
from backend.config import Config

logger = logging.getLogger(__name__)


def get_db() -> sqlite3.Connection:
    """Create a new SQLite connection with row factory."""
    conn = sqlite3.connect(Config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Initialize the database schema."""
    conn = get_db()
    cursor = conn.cursor()

    # 1. Create tables with IF NOT EXISTS (base schema)
    cursor.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'company',
            created_at DATETIME DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS employee_invitations (
            id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
            company_id TEXT NOT NULL,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            token TEXT UNIQUE NOT NULL,
            is_used INTEGER DEFAULT 0,
            created_at DATETIME DEFAULT (datetime('now')),
            FOREIGN KEY (company_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS api_endpoints (
            id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            url TEXT NOT NULL,
            method TEXT DEFAULT 'GET',
            interval INTEGER DEFAULT 60,
            is_active INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS monitoring_logs (
            id TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
            endpoint_id TEXT NOT NULL,
            status_code INTEGER DEFAULT 0,
            response_time REAL,
            is_success INTEGER DEFAULT 0,
            checked_at DATETIME DEFAULT (datetime('now')),
            FOREIGN KEY (endpoint_id) REFERENCES api_endpoints(id) ON DELETE CASCADE
        );
    """
    )

    # 2. Safe migrations: add new columns to existing users table if they don't exist
    def add_column_if_missing(table, column, definition):
        try:
            cursor.execute(f"SELECT {column} FROM {table} LIMIT 1")
        except Exception:
            logger.info(f"Adding column {column} to table {table}")
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    add_column_if_missing("users", "role", "TEXT DEFAULT 'company'")
    add_column_if_missing("users", "company_id", "TEXT")
    add_column_if_missing("users", "employee_id", "TEXT")

    # Create email_verifications table for OTP-based registration
    cursor.executescript(
        """
        CREATE TABLE IF NOT EXISTS email_verifications (
            id      TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(16)))),
            email   TEXT NOT NULL,
            otp     TEXT NOT NULL,
            is_used INTEGER DEFAULT 0,
            expires_at DATETIME NOT NULL,
            created_at DATETIME DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_email_verif_email ON email_verifications(email);
    """
    )

    # 3. Create indices (now that columns definitely exist)
    cursor.executescript(
        """
        CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
        CREATE INDEX IF NOT EXISTS idx_users_employee_id ON users(employee_id);
        CREATE INDEX IF NOT EXISTS idx_invitations_token ON employee_invitations(token);
        CREATE INDEX IF NOT EXISTS idx_endpoints_user_id ON api_endpoints(user_id);
        CREATE INDEX IF NOT EXISTS idx_logs_endpoint_id ON monitoring_logs(endpoint_id);
        CREATE INDEX IF NOT EXISTS idx_logs_checked_at ON monitoring_logs(checked_at);
    """
    )

    conn.commit()
    conn.close()
    logger.info(f"Database initialized at {Config.DATABASE_PATH}")


def row_to_dict(row) -> dict:
    """Convert a sqlite3.Row to a regular dict."""
    if row is None:
        return None
    return dict(row)


def rows_to_list(rows) -> list:
    """Convert a list of sqlite3.Row to a list of dicts."""
    return [dict(r) for r in rows]
