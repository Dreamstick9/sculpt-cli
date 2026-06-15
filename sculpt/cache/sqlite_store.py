"""Content-addressed cache for sculpt."""

import hashlib
import json
import sqlite3
import time
from pathlib import Path
from typing import Optional

from ..models import GenerationParams


class CacheStore:
    """SQLite-backed content-addressed cache."""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self) -> None:
        """Initialize cache database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    model TEXT NOT NULL,
                    params_json TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    created_ts REAL NOT NULL,
                    access_count INTEGER DEFAULT 0,
                    last_access_ts REAL NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_model ON cache(model)
            """)
            conn.commit()
    
    @staticmethod
    def make_key(image_path: Path, model: str, params: GenerationParams) -> str:
        """Generate cache key from image content + model + params."""
        # Hash image content
        with open(image_path, "rb") as f:
            image_hash = hashlib.sha256(f.read()).hexdigest()[:16]
        
        # Hash params
        param_dict = {
            "texture_resolution": params.texture_resolution,
            "remesh": params.remesh,
            "quality": params.quality,
            "geometry": params.geometry,
            "fast": params.fast,
        }
        params_json = json.dumps(param_dict, sort_keys=True)
        params_hash = hashlib.sha256(params_json.encode()).hexdigest()[:16]
        
        return f"{image_hash}_{model}_{params_hash}"
    
    def get(self, key: str) -> Optional[Path]:
        """Get cached file path if exists and valid."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT file_path, file_size FROM cache WHERE key = ?",
                (key,)
            )
            row = cursor.fetchone()
            
            if row:
                file_path = Path(row["file_path"])
                expected_size = row["file_size"]
                
                # Verify file still exists and hasn't been corrupted
                if file_path.exists() and file_path.stat().st_size == expected_size:
                    # Update access stats
                    now = time.time()
                    conn.execute(
                        "UPDATE cache SET access_count = access_count + 1, last_access_ts = ? WHERE key = ?",
                        (now, key)
                    )
                    conn.commit()
                    return file_path
                
                # File missing or corrupted - remove from cache
                conn.execute("DELETE FROM cache WHERE key = ?", (key,))
                conn.commit()
        
        return None
    
    def put(self, key: str, model: str, params: GenerationParams, file_path: Path) -> None:
        """Store cache entry."""
        file_size = file_path.stat().st_size if file_path.exists() else 0
        param_dict = {
            "texture_resolution": params.texture_resolution,
            "remesh": params.remesh,
            "quality": params.quality,
            "geometry": params.geometry,
            "fast": params.fast,
        }
        params_json = json.dumps(param_dict, sort_keys=True)
        now = time.time()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO cache 
                (key, model, params_json, file_path, file_size, created_ts, last_access_ts)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                key, model, json.dumps({
                    "texture_resolution": params.texture_resolution,
                    "remesh": params.remesh,
                    "quality": params.quality,
                    "geometry": params.geometry,
                    "fast": params.fast,
                }, sort_keys=True), str(file_path), 
                file_path.stat().st_size if file_path.exists() else 0,
                now, now
            ))
            conn.commit()
    
    def stats(self) -> dict:
        """Get cache statistics."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT COUNT(*) as entries,
                       SUM(file_size) as total_bytes,
                       SUM(access_count) as total_hits,
                       AVG(access_count) as avg_hits
                FROM cache
            """)
            row = cursor.fetchone()
            return {
                "entries": row["entries"] or 0,
                "total_bytes": row["total_bytes"] or 0,
                "total_hits": row["total_hits"] or 0,
                "avg_hits": row["avg_hits"] or 0,
            }
    
    def purge(self) -> int:
        """Remove all cache entries. Returns count deleted."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM cache")
            conn.commit()
            return cursor.rowcount


def get_cache_store() -> CacheStore:
    """Get global cache store instance."""
    from ..config import CACHE_FILE
    return CacheStore(CACHE_FILE)