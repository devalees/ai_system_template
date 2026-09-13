"""Document attachment business service coordinating database records and blob storage."""

import uuid
from typing import Optional, List, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.context import get_active_company_id
from modules.base.documents.models import DocumentAttachment
from modules.base.documents.storage import StorageEngine


class DocumentService:
    """Service managing document attachment lifecycles, hashing, and CAS retrieval."""

    @classmethod
    async def create_attachment(
        cls,
        db: AsyncSession,
        name: str,
        content: bytes,
        mime_type: str = "application/octet-stream",
        company_id: Optional[uuid.UUID] = None,
        res_model: Optional[str] = None,
        res_id: Optional[uuid.UUID] = None,
        description: Optional[str] = None,
    ) -> DocumentAttachment:
        """Persist binary blob to content-addressable storage and insert attachment record."""
        target_company_id = company_id or get_active_company_id()
        if not target_company_id:
            raise ValueError("Target company_id is required to create document attachment.")

        storage_path, file_hash, file_size = await StorageEngine.save_blob(
            content=content,
            company_id=target_company_id,
        )

        attachment = DocumentAttachment(
            company_id=target_company_id,
            name=name,
            file_hash=file_hash,
            file_size=file_size,
            mime_type=mime_type,
            storage_path=storage_path,
            res_model=res_model.lower() if res_model else None,
            res_id=res_id,
            description=description,
        )
        db.add(attachment)
        await db.commit()
        await db.refresh(attachment)
        return attachment

    @classmethod
    async def get_attachment(
        cls,
        db: AsyncSession,
        attachment_id: uuid.UUID,
        company_id: uuid.UUID,
    ) -> Optional[DocumentAttachment]:
        """Fetch attachment record scoped to tenant company."""
        stmt = select(DocumentAttachment).where(
            DocumentAttachment.id == attachment_id,
            DocumentAttachment.company_id == company_id,
        )
        return (await db.execute(stmt)).scalar_one_or_none()

    @classmethod
    async def get_entity_attachments(
        cls,
        db: AsyncSession,
        res_model: str,
        res_id: uuid.UUID,
        company_id: uuid.UUID,
    ) -> List[DocumentAttachment]:
        """Fetch all attachments associated with a polymorphic model record."""
        stmt = select(DocumentAttachment).where(
            DocumentAttachment.company_id == company_id,
            DocumentAttachment.res_model == res_model.lower(),
            DocumentAttachment.res_id == res_id,
        ).order_by(DocumentAttachment.created_at.desc())
        return (await db.execute(stmt)).scalars().all()

    @classmethod
    async def read_attachment_bytes(
        cls,
        db: AsyncSession,
        attachment_id: uuid.UUID,
        company_id: uuid.UUID,
    ) -> Tuple[DocumentAttachment, bytes]:
        """Retrieve attachment record and stream raw binary bytes."""
        attachment = await cls.get_attachment(db, attachment_id, company_id)
        if not attachment:
            raise ValueError("Attachment not found.")

        content = await StorageEngine.read_blob(attachment.storage_path)
        return attachment, content
