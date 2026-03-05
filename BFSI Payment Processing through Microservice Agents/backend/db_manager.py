"""
db_manager.py
Handles database connections, queries, and transaction management.
"""
import json
import sqlite3
from contextlib import contextmanager
from typing import Any, List, Dict, Optional
from pathlib import Path

DB_PATH = "../data/payment_system.db"  # Update with your DB path
POLICIES_DIR = Path("../data/bank_policies")
# ===================================================================
# Database Connection Management
# ===================================================================

@contextmanager
def get_connection(db_path: str = DB_PATH):
    """Context manager to get a database connection"""
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row  # Access rows as dictionaries
        yield conn
    except sqlite3.Error as e:
        print(f"[DB ERROR] {e}")
        raise
    finally:
        if conn:
            conn.commit()
            conn.close()

# ===================================================================
# Query Execution Utilities
# ===================================================================

def fetch_all(query: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
    """Fetch all rows for a query"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params or ())
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

def fetch_one(query: str, params: Optional[tuple] = None) -> Optional[Dict[str, Any]]:
    """Fetch a single row"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params or ())
        row = cursor.fetchone()
        return dict(row) if row else None

def execute_query(query: str, params: Optional[tuple] = None) -> int:
    """Execute INSERT/UPDATE/DELETE query and return affected rows"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, params or ())
        return cursor.rowcount

def execute_many(query: str, param_list: List[tuple]) -> int:
    """Execute multiple queries at once (bulk insert/update)"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.executemany(query, param_list)
        return cursor.rowcount

# ===================================================================
# Transaction Utilities
# ===================================================================

def begin_transaction(conn):
    """Begin a database transaction"""
    conn.execute("BEGIN TRANSACTION;")

def commit_transaction(conn):
    """Commit a database transaction"""
    conn.commit()

def rollback_transaction(conn):
    """Rollback a database transaction"""
    conn.rollback()

# ===================================================================
# Table Management / Initialization
# ===================================================================

def initialize_database():
    """Create tables if they don't exist"""
    queries = [
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            name TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS transactions (
            transaction_id TEXT PRIMARY KEY,
            user_id INTEGER,
            amount REAL,
            status TEXT,
            category TEXT,
            risk_score INTEGER,
            created_at TEXT,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS policies (
            policy_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_type TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS ai_logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            agent_name TEXT NOT NULL,
            agent_type TEXT,
            operation TEXT,
            input_data TEXT,
            output_data TEXT,
            execution_time REAL,
            status TEXT DEFAULT 'success',
            error_message TEXT,
            user_id INTEGER,
            transaction_id TEXT,
            model_used TEXT,
            tokens_used INTEGER,
            cost REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(user_id),
            FOREIGN KEY(transaction_id) REFERENCES transactions(transaction_id)
        );
        """
    ]
    with get_connection() as conn:
        cursor = conn.cursor()
        for q in queries:
            cursor.execute(q)
        print("[DB INIT] Database initialized successfully")


# ===================================================================
# Example Helper Functions
# ===================================================================

def add_user(email: str, name: str) -> int:
    """Insert a new user"""
    query = "INSERT INTO users (email, name) VALUES (?, ?)"
    return execute_query(query, (email, name))

def add_transaction(transaction: Dict[str, Any]) -> int:
    """Insert a transaction"""
    query = """
    INSERT INTO transactions
    (transaction_id, user_id, amount, status, category, risk_score, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    params = (
        transaction.get("transaction_id"),
        transaction.get("user_id"),
        transaction.get("amount"),
        transaction.get("status"),
        transaction.get("category"),
        transaction.get("risk_score"),
        transaction.get("created_at")
    )
    return execute_query(query, params)

def get_transactions_for_user(user_id: int) -> List[Dict[str, Any]]:
    """Fetch all transactions for a specific user"""
    query = "SELECT * FROM transactions WHERE user_id = ? ORDER BY created_at DESC"
    return fetch_all(query, (user_id,))

# ===================================================================
# Policy Management
# ===================================================================

def register_policy(name: str, file_name: str) -> int:
    """Register or update a policy file in the DB"""
    file_path = POLICIES_DIR / file_name
    if not file_path.exists():
        raise FileNotFoundError(f"Policy file {file_path} not found")

    file_type = file_path.suffix.lower().replace(".", "")
    query = """
    INSERT INTO policies (name, file_path, file_type, updated_at)
    VALUES (?, ?, ?, datetime('now'))
    ON CONFLICT(name) DO UPDATE SET
        file_path = excluded.file_path,
        file_type = excluded.file_type,
        updated_at = datetime('now')
    """
    return execute_query(query, (name, str(file_path), file_type))

def update_policy_content(policy_id: int, new_content: str) -> int:
    """Update content of a TXT policy file"""
    policy = fetch_one("SELECT * FROM policies WHERE policy_id = ?", (policy_id,))
    if not policy:
        raise ValueError("Policy not found")

    file_path = Path(policy["file_path"])
    if policy["file_type"] != "txt":
        raise ValueError("Only TXT policies can be updated")

    file_path.write_text(new_content, encoding="utf-8")

    query = "UPDATE policies SET updated_at = datetime('now') WHERE policy_id = ?"
    return execute_query(query, (policy_id,))


def list_policies() -> List[Dict[str, Any]]:
    """Return all registered policies"""
    return fetch_all("SELECT * FROM policies ORDER BY created_at DESC")


def get_policy_content(policy_id: int) -> Optional[Dict[str, Any]]:
    """
    Fetch a policy with content or file path.
    """
    policy = fetch_one("SELECT * FROM policies WHERE policy_id = ?", (policy_id,))
    if not policy:
        return None

    file_path = Path(policy["file_path"])
    if not file_path.exists():
        return None

    if policy["file_type"] == "txt":
        content = file_path.read_text(encoding="utf-8")
    else:
        content = None  # PDFs handled separately in frontend

    return {**policy, "content": content}



def seed_policies():
    """
    Register initial policies from data/bank_policies/.
    Run this once after DB init.
    """
    policies = [
        ("Privacy Policy", "Privacy Policy.txt"),
        ("Refund Policy", "Refund Policy.pdf"),
        ("Terms and Conditions", "Terms and Conditions.txt"),
    ]
    for name, file_name in policies:
        try:
            register_policy(name, file_name)
        except Exception as e:
            print(f"[DB SEED] Skipping {name}: {e}")

def delete_policy(policy_id: int) -> int:
    """Delete a policy by ID"""
    query = "DELETE FROM policies WHERE policy_id = ?"
    return execute_query(query, (policy_id,))

# ===================================================================
# AI Logs Management
# ===================================================================

def add_ai_log(log: Dict[str, Any]) -> int:
    """Insert a new AI log entry with JSON-safe input/output fields"""
    query = """
    INSERT INTO ai_logs (
        session_id, agent_name, agent_type, operation,
        input_data, output_data, execution_time, status,
        error_message, user_id, transaction_id, model_used,
        tokens_used, cost, created_at
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
    """
    params = (
        log.get("session_id"),
        log.get("agent_name"),
        log.get("agent_type"),
        log.get("operation"),
        json.dumps(log.get("input_data")) if log.get("input_data") is not None else None,
        json.dumps(log.get("output_data")) if log.get("output_data") is not None else None,
        log.get("execution_time"),
        log.get("status", "success"),
        log.get("error_message"),
        log.get("user_id"),
        log.get("transaction_id"),
        log.get("model_used"),
        log.get("tokens_used"),
        log.get("cost")
    )
    return execute_query(query, params)


def _parse_ai_log_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Helper: safely parse JSON fields in ai_logs"""
    for field in ["input_data", "output_data"]:
        if row.get(field):
            try:
                row[field] = json.loads(row[field])
            except json.JSONDecodeError:
                pass
    return row


def get_ai_logs(limit: int = 50) -> List[Dict[str, Any]]:
    """Fetch recent AI logs with parsed JSON fields"""
    rows = fetch_all("SELECT * FROM ai_logs ORDER BY created_at DESC LIMIT ?", (limit,))
    return [_parse_ai_log_row(r) for r in rows]


def get_ai_logs_for_user(user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    """Fetch AI logs for a specific user with parsed JSON fields"""
    rows = fetch_all(
        "SELECT * FROM ai_logs WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
        (user_id, limit)
    )
    return [_parse_ai_log_row(r) for r in rows]


def get_ai_system_stats() -> Dict[str, Any]:
    """Get aggregated AI system statistics"""
    total = fetch_one("SELECT COUNT(*) as total FROM ai_logs")["total"]
    success = fetch_one("SELECT COUNT(*) as success FROM ai_logs WHERE status = 'success'")["success"]
    avg_time = fetch_one("SELECT AVG(execution_time) as avg_time FROM ai_logs")["avg_time"]
    errors_24h = fetch_one("""
        SELECT COUNT(*) as errors_24h 
        FROM ai_logs 
        WHERE status = 'error' AND created_at >= datetime('now', '-1 day')
    """)["errors_24h"]

    success_rate = (success / total * 100) if total > 0 else 0

    return {
        "total_operations": total,
        "success_rate": round(success_rate, 2),
        "avg_response_time": round(avg_time or 0, 3),
        "errors_24h": errors_24h
    }
