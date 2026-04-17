import os
import logging
import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from backend.config import Config

logger = logging.getLogger(__name__)

# Global connection pool
db_pool = None

def get_db():
    """Get a connection from the PostgreSQL pool."""
    global db_pool
    if db_pool is None:
        init_pool()
    return db_pool.getconn()

def release_db(conn):
    """Release a connection back to the PostgreSQL pool."""
    global db_pool
    if db_pool and conn:
        db_pool.putconn(conn)

def init_pool():
    """Initialize the PostgreSQL connection pool."""
    global db_pool
    if db_pool is None:
        if not Config.DATABASE_URL:
            logger.error("DATABASE_URL environment variable is not set. Database operations will fail.")
            raise RuntimeError("DATABASE_URL is not set.")

        is_vercel = os.getenv("VERCEL") == "1"
        # On Vercel, we want essentially 1 connection per lambda to avoid exhausting Supabase limits
        min_conn = 0 if is_vercel else Config.DB_POOL_MIN
        max_conn = 1 if is_vercel else Config.DB_POOL_MAX

        try:
            db_pool = psycopg2.pool.ThreadedConnectionPool(
                minconn=min_conn,
                maxconn=max_conn,
                dsn=Config.DATABASE_URL,
                cursor_factory=RealDictCursor
            )
            logger.info(f"PostgreSQL connection pool created (Vercel={is_vercel}, Min={min_conn}, Max={max_conn})")
        except Exception as e:
            logger.error(f"Failed to create PostgreSQL pool: {e}")
            raise

def close_pool():
    """Close all connections in the pool."""
    global db_pool
    if db_pool is not None:
        db_pool.closeall()
        logger.info("PostgreSQL connection pool closed")

def init_db():
    """Initialize the PostgreSQL database schema."""
    init_pool()
    conn = get_db()
    cursor = conn.cursor()

    try:
        # PostgreSQL syntax for tables and defaults
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'company',
                company_id TEXT,
                employee_id TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS employee_invitations (
                id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
                company_id TEXT NOT NULL,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                token TEXT UNIQUE NOT NULL,
                is_used BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                FOREIGN KEY (company_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS api_endpoints (
                id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
                user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                url TEXT NOT NULL,
                method TEXT DEFAULT 'GET',
                interval INTEGER DEFAULT 60,
                is_active BOOLEAN DEFAULT TRUE,
                api_key TEXT,
                api_key_header TEXT DEFAULT 'Authorization',
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS monitoring_logs (
                id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
                endpoint_id TEXT NOT NULL,
                status_code INTEGER DEFAULT 0,
                response_time REAL,
                is_success BOOLEAN DEFAULT FALSE,
                api_key_status TEXT,
                checked_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                FOREIGN KEY (endpoint_id) REFERENCES api_endpoints(id) ON DELETE CASCADE
            );
            
            CREATE TABLE IF NOT EXISTS email_verifications (
                id TEXT PRIMARY KEY DEFAULT gen_random_uuid()::text,
                email TEXT NOT NULL,
                otp TEXT NOT NULL,
                is_used BOOLEAN DEFAULT FALSE,
                expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
            """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
            CREATE INDEX IF NOT EXISTS idx_users_employee_id ON users(employee_id);
            CREATE INDEX IF NOT EXISTS idx_invitations_token ON employee_invitations(token);
            CREATE INDEX IF NOT EXISTS idx_endpoints_user_id ON api_endpoints(user_id);
            CREATE INDEX IF NOT EXISTS idx_logs_endpoint_id ON monitoring_logs(endpoint_id);
            CREATE INDEX IF NOT EXISTS idx_logs_checked_at ON monitoring_logs(checked_at);
            CREATE INDEX IF NOT EXISTS idx_email_verif_email ON email_verifications(email);
            """
        )

        conn.commit()
        logger.info(f"PostgreSQL database initialized")
    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to initialize database: {e}")
        raise
    finally:
        cursor.close()
        release_db(conn)

def row_to_dict(row) -> dict:
    """Convert a psycopg2 RealDictRow to a regular dict."""
    if row is None:
        return None
    return dict(row)

def rows_to_list(rows) -> list:
    """Convert a list of psycopg2 RealDictRow to a list of dicts."""
    if rows is None:
        return []
    return [dict(r) for r in rows]
