"""Content-Addressable Storage (CAS) engine for document attachments."""

import uuid
import hashlib
import aiofiles
from pathlib import Path
from typing import Tuple

from core.config import settings

# Base filestore directory configured relative to app or environment
FILESTORE_ROOT = Path(__file__).resolve().parent.parent.parent.parent / "filestore"


class StorageEngine:
    """Async Content-Addressable Storage engine saving blobs by SHA-256 hash."""

    @classmethod
    def get_base_dir(cls) -> Path:
        """Resolve filestore base directory ensuring it exists."""
        base_dir = Path("/app/filestore") if Path("/app/filestore").exists() else FILESTORE_ROOT
        base_dir.mkdir(parents=True, exist_ok=True)
        return base_dir

    @classmethod
    async def save_blob(cls, content: bytes, company_id: uuid.UUID) -> Tuple[str, str, int]:
        """Save binary content to disk partitioned by company_id and SHA-256 hash prefix.

        Returns:
            Tuple of (relative_storage_path, sha256_hex_hash, file_size_bytes)
        """
        file_hash = hashlib.sha256(content).hexdigest()
        file_size = len(content)

        prefix = file_hash[:2]
        relative_path = f"{company_id}/{prefix}/{file_hash}"
        full_path = cls.get_base_dir() / relative_path

        # Deduplication: only write if file does not physically exist yet
        if not full_path.exists():
            full_path.parent.mkdir(parents=True, exist_ok=True)
            async with aiofiles.open(full_path, "wb") as f:
                await f.write(content)

        return relative_path, file_hash, file_size

    @classmethod
    async def read_blob(cls, storage_path: str) -> bytes:
        """Read binary content from storage path asynchronously."""
        full_path = cls.get_base_dir() / storage_path
        if not full_path.exists():
            raise FileNotFoundError(f"Blob not found at {storage_path}")

        async with aiofiles.open(full_path, "rb") as f:
            return await f.read()

    @classmethod
    async def delete_blob(cls, storage_path: str) -> bool:
        """Remove blob file from disk if it exists."""
        full_path = cls.get_base_dir() / storage_path
        if full_path.exists():
            full_path.unlink()
            return True
        return False
