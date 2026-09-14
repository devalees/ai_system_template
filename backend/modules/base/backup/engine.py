"""Packaging engine for atomic .tar.gz archives, SQL dumps, and SHA-256 integrity verification."""

import io
import json
import tarfile
import hashlib
import uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Tuple, Dict, Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from core.base_models import Base


class BackupEngine:
    """Handles raw SQL extraction, archive compression, and cryptographic validation."""

    @classmethod
    async def extract_tenant_sql_dump(cls, db: AsyncSession, company_id: uuid.UUID) -> str:
        """Extract multi-table DDL and tenant-scoped INSERT statements."""
        lines = [
            "-- ========================================================",
            "-- Sovereign Enterprise Platform Database Dump",
            f"-- Tenant ID: {company_id}",
            f"-- Generated At: {datetime.now(timezone.utc).isoformat()}",
            "-- ========================================================\n",
        ]

        # Iterate tables registered in SQLAlchemy metadata
        for table in Base.metadata.sorted_tables:
            table_name = table.name
            has_company_id = "company_id" in table.c

            if has_company_id:
                stmt = select(table).where(table.c.company_id == company_id)
            else:
                # Tables without company_id (e.g. global lookups or system fixtures)
                stmt = select(table)

            try:
                res = await db.execute(stmt)
                rows = res.mappings().all()

                if rows:
                    lines.append(f"\n-- Data for table: {table_name}")
                    for row in rows:
                        cols = list(row.keys())
                        col_names = ", ".join(f'"{c}"' for c in cols)
                        vals = []
                        for c in cols:
                            val = row[c]
                            if val is None:
                                vals.append("NULL")
                            elif isinstance(val, (int, float)):
                                vals.append(str(val))
                            elif isinstance(val, bool):
                                vals.append("TRUE" if val else "FALSE")
                            elif isinstance(val, (dict, list)):
                                json_str = json.dumps(val).replace("'", "''")
                                vals.append(f"'{json_str}'::jsonb")
                            else:
                                clean_val = str(val).replace("'", "''")
                                vals.append(f"'{clean_val}'")

                        val_str = ", ".join(vals)
                        lines.append(f'INSERT INTO "{table_name}" ({col_names}) VALUES ({val_str}) ON CONFLICT DO NOTHING;')
            except Exception:
                # If table doesn't exist yet or query fails, skip gracefully
                continue

        return "\n".join(lines)

    @classmethod
    def create_tar_archive(
        cls,
        output_path: str,
        sql_dump: str,
        filestore_files: List[Tuple[str, str]],  # (absolute_source_path, relative_tar_path)
        manifest_data: Dict[str, Any],
    ) -> Tuple[int, str]:
        """Pack SQL dump, files, and manifest.json into compressed .tar.gz bundle."""
        tar_path = Path(output_path)
        tar_path.parent.mkdir(parents=True, exist_ok=True)

        with tarfile.open(output_path, "w:gz") as tar:
            # 1. Add manifest.json
            manifest_bytes = json.dumps(manifest_data, indent=2).encode("utf-8")
            ti_manifest = tarfile.TarInfo(name="manifest.json")
            ti_manifest.size = len(manifest_bytes)
            ti_manifest.mtime = int(datetime.now(timezone.utc).timestamp())
            tar.addfile(ti_manifest, io.BytesIO(manifest_bytes))

            # 2. Add dump.sql
            sql_bytes = sql_dump.encode("utf-8")
            ti_sql = tarfile.TarInfo(name="dump.sql")
            ti_sql.size = len(sql_bytes)
            ti_sql.mtime = int(datetime.now(timezone.utc).timestamp())
            tar.addfile(ti_sql, io.BytesIO(sql_bytes))

            # 3. Add filestore attachments
            for abs_path, rel_name in filestore_files:
                p = Path(abs_path)
                if p.exists() and p.is_file():
                    tar.add(str(p), arcname=f"filestore/{rel_name}")

        # Compute SHA-256 and file size
        hasher = hashlib.sha256()
        file_size = 0
        with open(output_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
                file_size += len(chunk)

        checksum = hasher.hexdigest()
        return file_size, checksum

    @classmethod
    def verify_archive(cls, archive_path: str) -> Dict[str, Any]:
        """Verify .tar.gz bundle integrity, structure, and embedded manifest."""
        p = Path(archive_path)
        if not p.exists():
            raise FileNotFoundError(f"Archive '{archive_path}' not found")

        hasher = hashlib.sha256()
        with open(archive_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        calculated_checksum = hasher.hexdigest()

        with tarfile.open(archive_path, "r:gz") as tar:
            members = tar.getnames()
            if "manifest.json" not in members:
                raise ValueError("Archive is missing mandatory 'manifest.json' metadata")
            if "dump.sql" not in members:
                raise ValueError("Archive is missing mandatory 'dump.sql' database dump")

            manifest_file = tar.extractfile("manifest.json")
            if not manifest_file:
                raise ValueError("Could not read 'manifest.json'")
            manifest_dict = json.loads(manifest_file.read().decode("utf-8"))

        return {
            "valid": True,
            "checksum_sha256": calculated_checksum,
            "total_files": len(members),
            "archive_size": p.stat().st_size,
            "manifest": manifest_dict,
        }
