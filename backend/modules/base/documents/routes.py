"""API routes for Document & Blob Attachment Management."""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from modules.base.identity_rbac.dependencies import get_current_user
from modules.base.identity_rbac.models import User
from modules.base.documents.models import DocumentAttachment
from modules.base.documents.schemas import DocumentAttachmentRead, DocumentAttachmentUpdate
from modules.base.documents.service import DocumentService

router = APIRouter()


@router.post(
    "/upload",
    response_model=DocumentAttachmentRead,
    status_code=status.HTTP_201_CREATED,
    tags=["Document Attachments"],
    summary="Upload binary file attachment to content-addressable storage",
)
async def upload_attachment(
    file: UploadFile = File(..., description="Binary file upload"),
    res_model: Optional[str] = Form(None, description="Optional target entity model (e.g. invoice, contract)"),
    res_id: Optional[uuid.UUID] = Form(None, description="Optional target entity record UUID"),
    description: Optional[str] = Form(None, description="Optional description or note"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentAttachment:
    """Upload and hash binary file, saving to content-addressable filestore."""
    content = await file.read()
    filename = file.filename or "unnamed_attachment"
    mime_type = file.content_type or "application/octet-stream"

    return await DocumentService.create_attachment(
        db=db,
        name=filename,
        content=content,
        mime_type=mime_type,
        company_id=current_user.company_id,
        res_model=res_model,
        res_id=res_id,
        description=description,
    )


@router.get(
    "/{attachment_id}",
    response_model=DocumentAttachmentRead,
    tags=["Document Attachments"],
    summary="Get document attachment metadata",
)
async def get_attachment_metadata(
    attachment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentAttachment:
    """Retrieve metadata information for a single document attachment."""
    attachment = await DocumentService.get_attachment(db, attachment_id, current_user.company_id)
    if not attachment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found.")
    return attachment


@router.get(
    "/{attachment_id}/download",
    tags=["Document Attachments"],
    summary="Download raw binary file from content-addressable storage",
)
async def download_attachment_binary(
    attachment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Stream binary file content with appropriate Content-Disposition headers."""
    try:
        attachment, content = await DocumentService.read_attachment_bytes(
            db=db,
            attachment_id=attachment_id,
            company_id=current_user.company_id,
        )
        return Response(
            content=content,
            media_type=attachment.mime_type,
            headers={"Content-Disposition": f'attachment; filename="{attachment.name}"'},
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Physical blob file missing from filestore.")


@router.get(
    "/entity/{res_model}/{res_id}",
    response_model=List[DocumentAttachmentRead],
    tags=["Document Attachments"],
    summary="List all attachments attached to a business entity",
)
async def list_entity_attachments(
    res_model: str,
    res_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[DocumentAttachment]:
    """List all attachments associated with a specific entity record."""
    return await DocumentService.get_entity_attachments(
        db=db,
        res_model=res_model,
        res_id=res_id,
        company_id=current_user.company_id,
    )


@router.delete(
    "/{attachment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Document Attachments"],
    summary="Soft-delete a document attachment",
)
async def delete_attachment(
    attachment_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete attachment record while preserving CAS physical file for historical audit trails."""
    attachment = await DocumentService.get_attachment(db, attachment_id, current_user.company_id)
    if not attachment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found.")

    attachment.soft_delete(user_id=current_user.id)
    await db.commit()
    return None
