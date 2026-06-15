import sqlite3
import logging

logger = logging.getLogger(__name__)

MIGRATIONS = [
    # Migration 1: Initial migration schema creation
    """
    CREATE TABLE IF NOT EXISTS runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT UNIQUE NOT NULL,
        kind TEXT NOT NULL,
        status TEXT NOT NULL,
        topic TEXT,
        instructions_preview TEXT,
        pipeline_mode TEXT,
        web_search_enabled INTEGER DEFAULT 0,
        created_at TEXT NOT NULL,
        started_at TEXT,
        finished_at TEXT,
        output_dir TEXT,
        error_type TEXT,
        error_message TEXT,
        metadata_json TEXT
    );
    
    CREATE TABLE IF NOT EXISTS run_agents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
        role TEXT NOT NULL,
        provider TEXT,
        model TEXT,
        temperature REAL,
        agent_type TEXT,
        self_critique_enabled INTEGER DEFAULT 0,
        metadata_json TEXT
    );
    
    CREATE TABLE IF NOT EXISTS artifacts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
        artifact_type TEXT NOT NULL,
        path TEXT NOT NULL,
        relative_path TEXT NOT NULL,
        filename TEXT NOT NULL,
        mime_type TEXT,
        size_bytes INTEGER,
        sha256 TEXT,
        created_at TEXT NOT NULL,
        is_diagnostic INTEGER DEFAULT 0,
        metadata_json TEXT
    );
    
    CREATE TABLE IF NOT EXISTS runtime_snapshots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
        snapshot_type TEXT NOT NULL,
        version TEXT,
        fingerprint TEXT,
        metadata_json TEXT
    );
    
    CREATE TABLE IF NOT EXISTS sections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
        name TEXT NOT NULL,
        title TEXT,
        semantic_role TEXT,
        heading_policy TEXT,
        char_count INTEGER,
        order_index INTEGER,
        content_path TEXT,
        content_sha256 TEXT,
        metadata_json TEXT
    );
    
    CREATE TABLE IF NOT EXISTS sources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
        source_type TEXT NOT NULL,
        title TEXT,
        url TEXT,
        path TEXT,
        sha256 TEXT,
        used_by TEXT,
        metadata_json TEXT
    );
    
    CREATE TABLE IF NOT EXISTS evaluations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
        eval_type TEXT NOT NULL,
        status TEXT NOT NULL,
        summary TEXT,
        result_path TEXT,
        metadata_json TEXT,
        created_at TEXT NOT NULL
    );
    
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
        event_type TEXT NOT NULL,
        stage TEXT,
        message TEXT,
        created_at TEXT NOT NULL,
        metadata_json TEXT
    );
    """
]

def run_migrations(conn: sqlite3.Connection) -> None:
    """Run migrations on the connection sequentially under transactions."""
    conn.execute("PRAGMA foreign_keys = ON;")
    
    # Ensure schema_migrations exists
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY);"
    )
    
    cursor = conn.cursor()
    cursor.execute("SELECT version FROM schema_migrations ORDER BY version ASC;")
    applied = {row[0] for row in cursor.fetchall()}
    
    for idx, migration_sql in enumerate(MIGRATIONS, start=1):
        if idx in applied:
            continue
            
        logger.info("Applying SQLite Registry migration version %d...", idx)
        
        # Execute migration in a transaction manually
        try:
            conn.execute("BEGIN TRANSACTION;")
            conn.executescript(migration_sql)
            conn.execute("INSERT INTO schema_migrations (version) VALUES (?);", (idx,))
            conn.commit()
            logger.info("SQLite Registry migration version %d applied successfully.", idx)
        except Exception as e:
            conn.rollback()
            logger.error("Failed to apply SQLite Registry migration version %d: %s", idx, e)
            raise e
