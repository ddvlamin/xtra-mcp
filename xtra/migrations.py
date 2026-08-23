import sqlite3

def run_migrations(conn: sqlite3.Connection):
    """Runs database schema migrations on the SQLite connection."""
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(products)")
    columns = [col[1] for col in cursor.fetchall()]
    if "normalized_name" in columns and "query" not in columns:
        cursor.execute("ALTER TABLE products RENAME COLUMN normalized_name TO query")
    if "top_category_name" not in columns:
        cursor.execute("ALTER TABLE products ADD COLUMN top_category_name TEXT")
