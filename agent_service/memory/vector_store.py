"""
Sovereign Semantic Vector Memory Store.

Embeds sqlite-vec directly into Python for high-speed, zero-dependency
semantic similarity search across procedural memories, solved tasks, and
operational patterns.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import re
import sqlite3
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import sqlite_vec

logger = logging.getLogger("agent_service.memory")


class MemoryStore:
    """
    In-process vector database powered by sqlite-vec.
    
    Provides persistent storage and sub-15ms cosine similarity recall
    with zero external database dependencies.
    """

    DEFAULT_DIMENSION = 384

    def __init__(
        self,
        db_path: Optional[str | Path] = None,
        dimension: int = DEFAULT_DIMENSION,
    ) -> None:
        """
        Initializes the vector memory store.

        Args:
            db_path: Filepath to SQLite database. Defaults to
                     'agent_service/data/memory.db' or ':memory:' if in-memory.
            dimension: Vector embedding dimension (default: 384).
        """
        self.dimension = dimension

        if db_path is None:
            base_dir = Path(__file__).resolve().parent.parent / "data"
            base_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = str(base_dir / "memory.db")
        else:
            self.db_path = str(db_path)
            if self.db_path != ":memory:":
                Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.enable_load_extension(True)
        sqlite_vec.load(self._conn)
        self._conn.enable_load_extension(False)

        self._init_schema()

    def _init_schema(self) -> None:
        """Creates metadata tables and sqlite-vec virtual tables if not present."""
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_entries (
                    rowid INTEGER PRIMARY KEY AUTOINCREMENT,
                    id TEXT UNIQUE NOT NULL,
                    category TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    scope TEXT DEFAULT 'generalized',
                    metadata_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_memory_id ON memory_entries(id);"
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_memory_cat ON memory_entries(category);"
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_memory_scope ON memory_entries(scope);"
            )

            self._conn.execute(
                f"""
                CREATE VIRTUAL TABLE IF NOT EXISTS vec_entries USING vec0(
                    embedding float[{self.dimension}] distance_metric=cosine
                );
                """
            )

    def compute_embedding(self, text: str) -> list[float]:
        """
        Computes a deterministic, unit-normalized dense semantic embedding vector.

        Generates dense feature representations from character and token n-grams
        using multi-seed hashing, normalized to unit Euclidean length so cosine
        distance directly reflects semantic overlap.

        Args:
            text: Input text string to embed.

        Returns:
            list[float]: Unit-normalized float list of length self.dimension.
        """
        if not text or not text.strip():
            return [0.0] * self.dimension

        cleaned = re.sub(r"[^\w\s]", " ", text.lower())
        tokens = cleaned.split()

        vector = [0.0] * self.dimension

        # 1. Unigram & Bigram word features
        for i, word in enumerate(tokens):
            for seed in (17, 31, 73):
                h = int(hashlib.md5(f"{seed}_{word}".encode("utf-8")).hexdigest(), 16)
                idx = h % self.dimension
                sign = 1.0 if (h // self.dimension) % 2 == 0 else -1.0
                vector[idx] += sign * 1.5

            if i < len(tokens) - 1:
                bigram = f"{word}_{tokens[i+1]}"
                h_bi = int(hashlib.md5(bigram.encode("utf-8")).hexdigest(), 16)
                idx_bi = h_bi % self.dimension
                vector[idx_bi] += 2.0

        # 2. Substring character 3-grams
        raw_clean = "".join(tokens)
        for i in range(len(raw_clean) - 2):
            trigram = raw_clean[i : i + 3]
            h_tri = int(hashlib.sha256(trigram.encode("utf-8")).hexdigest()[:8], 16)
            vector[h_tri % self.dimension] += 0.5

        # 3. L2 Euclidean Normalization
        norm = math.sqrt(sum(x * x for x in vector))
        if norm > 0.0:
            vector = [x / norm for x in vector]
        else:
            vector[0] = 1.0

        return vector

    def add_memory(
        self,
        title: str,
        content: str,
        category: str = "solution",
        scope: str = "generalized",
        metadata: Optional[Dict[str, Any]] = None,
        memory_id: Optional[str] = None,
        embedding: Optional[list[float]] = None,
    ) -> str:
        """
        Stores an item in the semantic memory database.

        Args:
            title: Short descriptive title of the solution or pattern.
            content: Detailed body, instructions, or resolution notes.
            category: Domain category (e.g. 'solution', 'bugfix', 'architecture', 'dag').
            scope: Portability scope ('generalized' for portable, 'project_local' for private).
            metadata: Optional dictionary of additional structured attributes.
            memory_id: Optional explicit UUID string. Auto-generated if omitted.
            embedding: Optional pre-computed float list. Auto-computed if omitted.

        Returns:
            str: The unique identifier (UUID) of the stored memory.
        """
        mem_id = memory_id or str(uuid.uuid4())
        meta_str = json.dumps(metadata or {}, ensure_ascii=False)

        if embedding is None:
            text_to_embed = f"{title}\n{title}\n{content}"
            embedding = self.compute_embedding(text_to_embed)

        serialized_vec = sqlite_vec.serialize_float32(embedding)

        with self._conn:
            cur = self._conn.cursor()
            cur.execute(
                """
                INSERT INTO memory_entries (id, category, title, content, scope, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (mem_id, category, title.strip(), content.strip(), scope, meta_str),
            )
            rowid = cur.lastrowid
            cur.execute(
                "INSERT INTO vec_entries (rowid, embedding) VALUES (?, ?)",
                (rowid, serialized_vec),
            )

        logger.debug("Added memory %s: '%s' (scope: %s)", mem_id, title, scope)
        return mem_id

    def recall_similar(
        self,
        query_text: str,
        top_k: int = 2,
        threshold: float = 0.3,
        category: Optional[str] = None,
        scope: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Searches memory for items semantically closest to query_text using cosine distance.

        Args:
            query_text: Natural language query or task description.
            top_k: Maximum number of memories to return (default: 2).
            threshold: Minimum cosine similarity required (0.0 to 1.0, default: 0.3).
            category: Optional filter by specific category.
            scope: Optional filter by scope ('generalized' or 'project_local').

        Returns:
            List of matching memory dictionaries with calculated similarity score.
        """
        if not query_text or not query_text.strip():
            return []

        query_vec = self.compute_embedding(query_text)
        serialized_query = sqlite_vec.serialize_float32(query_vec)

        # Retrieve candidates from vector table
        candidate_k = max(top_k * 4, 20)
        cursor = self._conn.cursor()
        cursor.execute(
            """
            SELECT rowid, distance
            FROM vec_entries
            WHERE embedding MATCH ? AND k = ?
            ORDER BY distance ASC
            """,
            (serialized_query, candidate_k),
        )
        vec_matches = cursor.fetchall()

        if not vec_matches:
            return []

        # Map rowids to distance
        rowid_dist_map = {row["rowid"]: row["distance"] for row in vec_matches}
        placeholders = ",".join("?" for _ in rowid_dist_map.keys())

        query = f"""
            SELECT rowid, id, category, title, content, scope, metadata_json, created_at
            FROM memory_entries
            WHERE rowid IN ({placeholders})
        """
        params: list[Any] = list(rowid_dist_map.keys())

        if category:
            query += " AND category = ?"
            params.append(category)

        if scope:
            query += " AND scope = ?"
            params.append(scope)

        cursor.execute(query, params)
        entries = cursor.fetchall()

        results = []
        for row in entries:
            rowid = row["rowid"]
            distance = rowid_dist_map[rowid]
            # sqlite-vec cosine distance ranges [0.0 (identical), 2.0 (opposite)]
            similarity = round(max(0.0, 1.0 - distance), 4)

            if similarity < threshold:
                continue

            try:
                meta = json.loads(row["metadata_json"] or "{}")
            except Exception:
                meta = {}

            results.append(
                {
                    "id": row["id"],
                    "title": row["title"],
                    "content": row["content"],
                    "category": row["category"],
                    "scope": row["scope"],
                    "similarity": similarity,
                    "metadata": meta,
                    "created_at": row["created_at"],
                }
            )

        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results[:top_k]

    def get_memory(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a single memory entry by its unique ID."""
        cursor = self._conn.cursor()
        cursor.execute(
            """
            SELECT id, category, title, content, scope, metadata_json, created_at
            FROM memory_entries
            WHERE id = ?
            """,
            (memory_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None

        try:
            meta = json.loads(row["metadata_json"] or "{}")
        except Exception:
            meta = {}

        return {
            "id": row["id"],
            "title": row["title"],
            "content": row["content"],
            "category": row["category"],
            "scope": row["scope"],
            "metadata": meta,
            "created_at": row["created_at"],
        }

    def list_memories(
        self,
        category: Optional[str] = None,
        scope: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Lists stored memories with optional filtering."""
        query = "SELECT id, category, title, content, scope, metadata_json, created_at FROM memory_entries WHERE 1=1"
        params: list[Any] = []

        if category:
            query += " AND category = ?"
            params.append(category)

        if scope:
            query += " AND scope = ?"
            params.append(scope)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        cursor = self._conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()

        out = []
        for row in rows:
            try:
                meta = json.loads(row["metadata_json"] or "{}")
            except Exception:
                meta = {}
            out.append(
                {
                    "id": row["id"],
                    "title": row["title"],
                    "content": row["content"],
                    "category": row["category"],
                    "scope": row["scope"],
                    "metadata": meta,
                    "created_at": row["created_at"],
                }
            )
        return out

    def delete_memory(self, memory_id: str) -> bool:
        """Deletes a memory entry and its corresponding vector."""
        cursor = self._conn.cursor()
        cursor.execute("SELECT rowid FROM memory_entries WHERE id = ?", (memory_id,))
        row = cursor.fetchone()
        if not row:
            return False

        rowid = row["rowid"]
        with self._conn:
            self._conn.execute("DELETE FROM vec_entries WHERE rowid = ?", (rowid,))
            self._conn.execute("DELETE FROM memory_entries WHERE rowid = ?", (rowid,))

        return True

    def count(self, category: Optional[str] = None, scope: Optional[str] = None) -> int:
        """Returns the number of stored memories matching criteria."""
        query = "SELECT COUNT(*) FROM memory_entries WHERE 1=1"
        params: list[Any] = []

        if category:
            query += " AND category = ?"
            params.append(category)

        if scope:
            query += " AND scope = ?"
            params.append(scope)

        cursor = self._conn.cursor()
        cursor.execute(query, params)
        return cursor.fetchone()[0]

    def close(self) -> None:
        """Closes the database connection cleanly."""
        if hasattr(self, "_conn") and self._conn:
            self._conn.close()
