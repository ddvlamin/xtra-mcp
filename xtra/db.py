import os
import sqlite3
from typing import List, Optional
from rapidfuzz import process, fuzz, utils
from xtra.models import Product

DEFAULT_DB_PATH = os.path.join("resources", "colruyt_products.db")

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
            CREATE TABLE IF NOT EXISTS products (
                normalized_name TEXT PRIMARY KEY,
                product_id TEXT NOT NULL,
                product_name TEXT NOT NULL,
                product_brand TEXT,
                product_description TEXT,
                conservation_info TEXT,
                usage_info TEXT,
                content TEXT,
                top_category_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cursor.execute("PRAGMA table_info(products)")
        columns = [col[1] for col in cursor.fetchall()]
        if "top_category_name" not in columns:
            cursor.execute("ALTER TABLE products ADD COLUMN top_category_name TEXT")
        conn.commit()
        if self.db_path != ":memory:":
            conn.close()

    def store_product(self, product: Product) -> Product:
        """Validates unified Product fields and persists it in SQLite."""
        if not product:
            raise ValueError("Product object must be provided.")
        if not product.product_id:
            raise ValueError("Product product_id must be provided.")
        if not product.name:
            raise ValueError("Product name must be provided.")
        if not product.normalized_name:
            raise ValueError("Product normalized_name must be provided.")

        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO products (
                normalized_name, product_id, product_name, product_brand,
                product_description, conservation_info, usage_info, content,
                top_category_name
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(normalized_name) DO UPDATE SET
                product_id = excluded.product_id,
                product_name = excluded.product_name,
                product_brand = excluded.product_brand,
                product_description = excluded.product_description,
                conservation_info = excluded.conservation_info,
                usage_info = excluded.usage_info,
                content = excluded.content,
                top_category_name = excluded.top_category_name,
                created_at = CURRENT_TIMESTAMP
        """, (
            product.normalized_name,
            product.product_id,
            product.name,
            product.brand,
            product.description,
            product.conservation_info,
            product.usage_info,
            product.content,
            product.top_category_name
        ))
        conn.commit()
        if self.db_path != ":memory:":
            conn.close()

        return self.get_product(product.normalized_name) or product

    def get_product(self, normalized_name: str) -> Optional[Product]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM products WHERE normalized_name = ?", (normalized_name,))
        row = cursor.fetchone()
        result = self._row_to_product(row) if row else None
        if self.db_path != ":memory:":
            conn.close()
        return result

    def delete_product(self, normalized_name: Optional[str] = None, product_id: Optional[str] = None) -> int:
        """Deletes product(s) matching normalized_name or product_id.
        Returns the number of deleted rows.
        """
        if not normalized_name and not product_id:
            raise ValueError("Either normalized_name or product_id must be provided.")

        conn = self.get_connection()
        cursor = conn.cursor()
        if normalized_name and product_id:
            cursor.execute(
                "DELETE FROM products WHERE normalized_name = ? AND product_id = ?",
                (normalized_name, product_id)
            )
        elif normalized_name:
            cursor.execute(
                "DELETE FROM products WHERE normalized_name = ?",
                (normalized_name,)
            )
        else:
            cursor.execute(
                "DELETE FROM products WHERE product_id = ?",
                (product_id,)
            )
        deleted_count = cursor.rowcount
        conn.commit()
        if self.db_path != ":memory:":
            conn.close()
        return deleted_count

    def get_all_products(self) -> List[Product]:
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM products")
        rows = cursor.fetchall()
        result = [self._row_to_product(row) for row in rows]
        if self.db_path != ":memory:":
            conn.close()
        return result

    def find_product(self, query: str, score_threshold: int = 80) -> Optional[Product]:
        products = self.get_all_products()
        if not products:
            return None

        mapping_dict = {p.normalized_name: p for p in products if p.normalized_name}
        choices = list(mapping_dict.keys())
        
        result = process.extractOne(query, choices, scorer=fuzz.token_sort_ratio, processor=utils.default_process)
        if result:
            matched_key, score, _ = result
            if score >= score_threshold:
                return mapping_dict[matched_key]
        return None

    def _row_to_product(self, row: sqlite3.Row) -> Product:
        row_dict = dict(row)
        return Product(
            normalized_name=row_dict.get("normalized_name"),
            product_id=row_dict["product_id"],
            name=row_dict["product_name"],
            brand=row_dict.get("product_brand"),
            description=row_dict.get("product_description"),
            conservation_info=row_dict.get("conservation_info"),
            usage_info=row_dict.get("usage_info"),
            content=row_dict.get("content"),
            top_category_name=row_dict.get("top_category_name"),
            created_at=str(row_dict["created_at"]) if row_dict.get("created_at") else None
        )
