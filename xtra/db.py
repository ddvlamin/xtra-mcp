import os
import sqlite3
from typing import List, Optional
from rapidfuzz import process, fuzz
from xtra.models import ProductMapping

DEFAULT_DB_PATH = os.path.join("resources", "colruyt_mappings.db")

class Database:
    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or DEFAULT_DB_PATH
        self._conn: Optional[sqlite3.Connection] = None
        if self.db_path != ":memory:":
            dirname = os.path.dirname(self.db_path)
            if dirname:
                os.makedirs(dirname, exist_ok=True)
        else:
            self._conn = sqlite3.connect(":memory:")
            self._conn.row_factory = sqlite3.Row
        self.init_db()

    def get_connection(self) -> sqlite3.Connection:
        if self.db_path == ":memory:":
            return self._conn
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS product_mappings (
                cleaned_ingredient TEXT PRIMARY KEY,
                product_id TEXT NOT NULL,
                product_name TEXT NOT NULL,
                product_brand TEXT,
                product_description TEXT,
                conservation_info TEXT,
                usage_info TEXT,
                content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        if self.db_path != ":memory:":
            conn.close()

    def save_mapping(self, mapping: ProductMapping) -> ProductMapping:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO product_mappings (
                cleaned_ingredient, product_id, product_name, product_brand,
                product_description, conservation_info, usage_info, content
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(cleaned_ingredient) DO UPDATE SET
                product_id = excluded.product_id,
                product_name = excluded.product_name,
                product_brand = excluded.product_brand,
                product_description = excluded.product_description,
                conservation_info = excluded.conservation_info,
                usage_info = excluded.usage_info,
                content = excluded.content,
                created_at = CURRENT_TIMESTAMP
        """, (
            mapping.cleaned_ingredient,
            mapping.product_id,
            mapping.product_name,
            mapping.product_brand,
            mapping.product_description,
            mapping.conservation_info,
            mapping.usage_info,
            mapping.content
        ))
        conn.commit()
        if self.db_path != ":memory:":
            conn.close()
        return self.get_mapping(mapping.cleaned_ingredient) or mapping

    def get_mapping(self, cleaned_ingredient: str) -> Optional[ProductMapping]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM product_mappings WHERE cleaned_ingredient = ?", (cleaned_ingredient,))
        row = cursor.fetchone()
        result = ProductMapping(**dict(row)) if row else None
        if self.db_path != ":memory:":
            conn.close()
        return result

    def get_all_mappings(self) -> List[ProductMapping]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM product_mappings")
        rows = cursor.fetchall()
        result = [ProductMapping(**dict(row)) for row in rows]
        if self.db_path != ":memory:":
            conn.close()
        return result

    def find_fuzzy_mapping(self, query: str, score_threshold: int = 80) -> Optional[ProductMapping]:
        mappings = self.get_all_mappings()
        if not mappings:
            return None

        mapping_dict = {m.cleaned_ingredient: m for m in mappings}
        choices = list(mapping_dict.keys())
        
        result = process.extractOne(query, choices, scorer=fuzz.token_sort_ratio)
        if result:
            matched_key, score, _ = result
            if score >= score_threshold:
                return mapping_dict[matched_key]
        return None
