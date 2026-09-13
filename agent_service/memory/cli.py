"""
Knowledge CLI Tool for Sovereign Semantic Memory.

Provides command-line management for the sqlite-vec memory store:
- Exporting solved procedural tasks to JSONL (with automated secret/PII sanitization).
- Importing external knowledge JSONL files into the vector database.
- Performing semantic similarity queries directly against stored embeddings.
- Inspecting memory store distribution, counts, and category statistics.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from agent_service.memory.vector_store import MemoryStore
except (ImportError, ModuleNotFoundError):
    from memory.vector_store import MemoryStore  # type: ignore


# Sanitization patterns for stripping credentials, tokens, and PII on export
SENSITIVE_PATTERNS = [
    # API Keys & Bearer tokens
    (r"(?i)sk-[a-zA-Z0-9_-]{20,}", "[REDACTED_API_KEY]"),
    (r"(?i)(bearer\s+)[a-zA-Z0-9_\-\.]{20,}", r"\1[REDACTED_BEARER_TOKEN]"),
    (r"(?i)(api[_-]?key\s*[:=]\s*['\"]?)[a-zA-Z0-9_\-]{16,}(['\"]?)", r"\1[REDACTED_KEY]\2"),
    (r"(?i)(secret|password|passwd|token)\s*[:=]\s*['\"][^'\"]{6,}['\"]", r'\1="[REDACTED_SECRET]"'),
    # Private keys
    (r"-----BEGIN [A-Z ]+PRIVATE KEY-----[^-]+-----END [A-Z ]+PRIVATE KEY-----", "[REDACTED_PRIVATE_KEY]"),
    # IP Addresses (v4)
    (r"\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b", "[REDACTED_INTERNAL_IP]"),
    # Email addresses
    (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "[REDACTED_EMAIL]"),
]


def sanitize_text(text: str) -> str:
    """
    Sanitizes sensitive data, API keys, and PII from a given string.

    Args:
        text: Raw text string potentially containing confidential strings.

    Returns:
        str: Sanitized text with confidential strings replaced by redaction markers.
    """
    if not text:
        return ""
    sanitized = text
    for pattern, replacement in SENSITIVE_PATTERNS:
        sanitized = re.sub(pattern, replacement, sanitized)
    return sanitized


def sanitize_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively sanitizes values inside a dictionary.

    Args:
        data: Arbitrary dictionary to sanitize.

    Returns:
        Dict[str, Any]: Dictionary with sanitized string values.
    """
    clean: Dict[str, Any] = {}
    for k, v in data.items():
        if isinstance(v, str):
            clean[k] = sanitize_text(v)
        elif isinstance(v, dict):
            clean[k] = sanitize_dict(v)
        elif isinstance(v, list):
            clean[k] = [sanitize_text(item) if isinstance(item, str) else item for item in v]
        else:
            clean[k] = v
    return clean


def cmd_export(args: argparse.Namespace) -> int:
    """
    Exports memories of a given scope to a JSONL file after scrubbing sensitive data.

    Args:
        args: Parsed CLI arguments containing scope, output file path, and optional db_path.

    Returns:
        int: Exit status code (0 for success, non-zero for error).
    """
    store = MemoryStore(db_path=args.db_path)
    try:
        memories = store.list_memories(scope=args.scope, limit=100000)
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        exported_count = 0
        with open(output_path, "w", encoding="utf-8") as f:
            for item in memories:
                # Sanitize content, title, and metadata for export
                clean_item = {
                    "id": item["id"],
                    "title": sanitize_text(item["title"]),
                    "content": sanitize_text(item["content"]),
                    "category": item["category"],
                    "scope": item["scope"],
                    "metadata": sanitize_dict(item.get("metadata", {})),
                    "created_at": item.get("created_at"),
                }
                f.write(json.dumps(clean_item, ensure_ascii=False) + "\n")
                exported_count += 1

        print(f"Exported {exported_count} memories (scope: '{args.scope}') to {output_path}")
        return 0
    finally:
        store.close()


def cmd_import(args: argparse.Namespace) -> int:
    """
    Imports knowledge records from a JSONL file into the semantic vector store.

    Args:
        args: Parsed CLI arguments containing input file path and optional db_path.

    Returns:
        int: Exit status code (0 for success, non-zero for error).
    """
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file '{input_path}' does not exist.", file=sys.stderr)
        return 1

    store = MemoryStore(db_path=args.db_path)
    imported_count = 0
    skipped_count = 0

    try:
        with open(input_path, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    title = record.get("title", "")
                    content = record.get("content", "")
                    if not title or not content:
                        print(f"Warning: Line {line_no} missing title or content, skipping.")
                        skipped_count += 1
                        continue

                    # Check if ID already exists to prevent duplicate insertion
                    rec_id = record.get("id")
                    if rec_id and store.get_memory(rec_id):
                        skipped_count += 1
                        continue

                    store.add_memory(
                        title=title,
                        content=content,
                        category=record.get("category", "solution"),
                        scope=record.get("scope", "generalized"),
                        metadata=record.get("metadata", {}),
                        memory_id=rec_id,
                    )
                    imported_count += 1
                except Exception as exc:
                    print(f"Error parsing line {line_no}: {exc}", file=sys.stderr)
                    skipped_count += 1

        print(f"Import complete: {imported_count} imported, {skipped_count} skipped.")
        return 0
    finally:
        store.close()


def cmd_query(args: argparse.Namespace) -> int:
    """
    Performs cosine similarity search against stored memories and prints ranked matches.

    Args:
        args: Parsed CLI arguments containing query text, top_k, threshold, filters.

    Returns:
        int: Exit status code (0 for success).
    """
    store = MemoryStore(db_path=args.db_path)
    try:
        results = store.recall_similar(
            query_text=args.query,
            top_k=args.top_k,
            threshold=args.threshold,
            category=args.category,
            scope=args.scope,
        )

        print(f"Query: '{args.query}' (found {len(results)} matches, threshold={args.threshold})")
        print("=" * 70)

        if not results:
            print("No matching memories found exceeding the similarity threshold.")
            return 0

        for i, match in enumerate(results, 1):
            score = match["similarity"]
            pct = int(score * 100)
            print(f"[{i}] Similarity: {score:.4f} ({pct}%) | Category: [{match['category']}] | Scope: [{match['scope']}]")
            print(f"    ID:    {match['id']}")
            print(f"    Title: {match['title']}")
            snippet = match["content"].replace("\n", " ")
            if len(snippet) > 140:
                snippet = snippet[:140] + "..."
            print(f"    Body:  {snippet}")
            if match.get("metadata"):
                print(f"    Meta:  {match['metadata']}")
            print("-" * 70)

        return 0
    finally:
        store.close()


def cmd_stats(args: argparse.Namespace) -> int:
    """
    Outputs distribution statistics and total record counts of the vector memory store.

    Args:
        args: Parsed CLI arguments containing optional db_path.

    Returns:
        int: Exit status code (0 for success).
    """
    store = MemoryStore(db_path=args.db_path)
    try:
        total = store.count()
        gen_count = store.count(scope="generalized")
        local_count = store.count(scope="project_local")

        print("Sovereign Vector Memory Store Statistics")
        print("=" * 45)
        print(f"Database Path:    {store.db_path}")
        print(f"Vector Dimension: {store.dimension}")
        print(f"Total Entries:    {total}")
        print(f"  - Generalized:  {gen_count}")
        print(f"  - Project Local:{local_count}")
        print("-" * 45)

        # Category breakdown
        cursor = store._conn.cursor()
        cursor.execute("SELECT category, count(*) FROM memory_entries GROUP BY category ORDER BY count(*) DESC")
        cat_rows = cursor.fetchall()

        if cat_rows:
            print("Distribution by Category:")
            for row in cat_rows:
                print(f"  - {row[0]:<20}: {row[1]}")
        else:
            print("Distribution by Category: (no entries)")

        return 0
    finally:
        store.close()


def build_parser() -> argparse.ArgumentParser:
    """Constructs the command-line argument parser for knowledge memory operations."""
    parser = argparse.ArgumentParser(
        prog="python -m agent_service.memory.cli",
        description="Sovereign Semantic Vector Memory Store CLI",
    )
    parser.add_argument("--db-path", default=None, help="Custom SQLite DB path (defaults to data/memory.db)")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # export
    export_p = subparsers.add_parser("export", help="Export sanitized knowledge entries to JSONL")
    export_p.add_argument("--scope", default="generalized", help="Memory scope to export (default: generalized)")
    export_p.add_argument("--output", "-o", required=True, help="Destination JSONL filepath")

    # import
    import_p = subparsers.add_parser("import", help="Import knowledge entries from JSONL")
    import_p.add_argument("--input", "-i", required=True, help="Source JSONL filepath")

    # query
    query_p = subparsers.add_parser("query", help="Semantic similarity search query")
    query_p.add_argument("query", help="Text to query against memory embeddings")
    query_p.add_argument("--top-k", type=int, default=3, help="Max number of matches to return (default: 3)")
    query_p.add_argument("--threshold", type=float, default=0.3, help="Minimum cosine similarity threshold (default: 0.3)")
    query_p.add_argument("--category", default=None, help="Filter by category")
    query_p.add_argument("--scope", default=None, help="Filter by scope")

    # stats
    subparsers.add_parser("stats", help="Show memory store counts and category distribution")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    """Main CLI execution entrypoint."""
    parser = build_parser()
    args = parser.parse_args(argv)

    handlers = {
        "export": cmd_export,
        "import": cmd_import,
        "query": cmd_query,
        "stats": cmd_stats,
    }

    handler = handlers.get(args.command)
    if handler:
        return handler(args)
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
