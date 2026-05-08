"""
Audit logger for every data fetch.
Logs URL, timestamp, robots.txt result, and outcome.
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
import sqlite3

logger = logging.getLogger(__name__)


class AuditLogger:
    """
    Logs every fetch operation for compliance auditing.
    SQLite backend with JSON export.
    """
    
    def __init__(self, db_path: str = "./output/audit.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """Initialize SQLite audit database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    operation TEXT NOT NULL,
                    url TEXT,
                    domain TEXT,
                    robots_allowed BOOLEAN,
                    robots_checked_at TEXT,
                    robots_reason TEXT,
                    crawl_delay REAL,
                    status_code INTEGER,
                    response_size INTEGER,
                    error TEXT,
                    source_api TEXT,
                    record_id TEXT,
                    metadata TEXT
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS erasure_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    record_id TEXT NOT NULL,
                    reason TEXT,
                    requested_by TEXT,
                    action TEXT NOT NULL
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_url ON audit_log(url)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_record ON audit_log(record_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_erasure_record ON erasure_log(record_id)
            """)
            conn.commit()
    
    def log_fetch(
        self,
        operation: str,
        url: str,
        domain: str,
        robots_result: Optional[Dict] = None,
        status_code: Optional[int] = None,
        response_size: Optional[int] = None,
        error: Optional[str] = None,
        source_api: Optional[str] = None,
        record_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ):
        """Log a fetch operation."""
        now = datetime.utcnow().isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO audit_log (
                    timestamp, operation, url, domain, robots_allowed,
                    robots_checked_at, robots_reason, crawl_delay,
                    status_code, response_size, error, source_api,
                    record_id, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                now,
                operation,
                url,
                domain,
                robots_result.get("allowed") if robots_result else None,
                robots_result.get("checked_at") if robots_result else None,
                robots_result.get("reason") if robots_result else None,
                robots_result.get("crawl_delay") if robots_result else None,
                status_code,
                response_size,
                error,
                source_api,
                record_id,
                json.dumps(metadata) if metadata else None,
            ))
            conn.commit()
        
        logger.debug(f"Audit logged: {operation} {url}")
    
    def log_erasure(
        self,
        record_id: str,
        reason: str,
        requested_by: Optional[str] = None,
    ):
        """Log a data erasure request."""
        now = datetime.utcnow().isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO erasure_log (timestamp, record_id, reason, requested_by, action)
                VALUES (?, ?, ?, ?, ?)
            """, (now, record_id, reason, requested_by, "erased"))
            conn.commit()
        
        logger.info(f"Erasure logged for record {record_id}")
    
    def get_audit_for_record(self, record_id: Optional[str]) -> list:
        """Get all audit entries for a record."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            if record_id is None:
                cursor = conn.execute(
                    "SELECT * FROM audit_log WHERE record_id IS NULL ORDER BY timestamp"
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM audit_log WHERE record_id = ? ORDER BY timestamp",
                    (record_id,)
                )
            return [dict(row) for row in cursor.fetchall()]
    
    def export_to_json(self, output_path: str) -> str:
        """Export full audit log to JSON."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            audit = conn.execute("SELECT * FROM audit_log ORDER BY timestamp").fetchall()
            erasures = conn.execute("SELECT * FROM erasure_log ORDER BY timestamp").fetchall()
            
            data = {
                "exported_at": datetime.utcnow().isoformat(),
                "audit_entries": [dict(row) for row in audit],
                "erasure_entries": [dict(row) for row in erasures],
            }
        
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2, default=str)
        
        return output_path