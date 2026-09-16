"""REST API routes for Universal Party & Contact Engine."""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from modules.base.identity_rbac.dependencies import get_current_user
from modules.base.identity_rbac.models import User
from modules.base.parties.service import PartyService
from modules.base.parties.schemas import (
    PartyCreate,
    PartyUpdate,
    PartyRead,
    PartyContactCreate,
    PartyContactUpdate,
    PartyContactRead,
    PartyHierarchyNode,
)

router = APIRouter(prefix="", tags=["Universal Party & Contact Engine"])


@router.post(
    "/",
    response_model=PartyRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create Party",
    description="Register a new unified partner (customer, vendor, or internal affiliate) with optional initial contacts.",
)
async def create_party(
    payload: PartyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PartyRead:
    """Create a new unified party record."""
    return await PartyService.create_party(db, current_user.company_id, payload)


@router.get(
    "/",
    response_model=List[PartyRead],
    summary="List Parties",
    description="Query parties with optional role filters (is_customer, is_vendor), parent holding filter, and name search.",
)
async def list_parties(
    is_customer: Optional[bool] = Query(None, description="Filter for customers"),
    is_vendor: Optional[bool] = Query(None, description="Filter for vendors / suppliers"),
    parent_id: Optional[uuid.UUID] = Query(None, description="Filter by parent holding company ID"),
    search: Optional[str] = Query(None, description="Search party name case-insensitively"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[PartyRead]:
    """Retrieve parties for active company."""
    return await PartyService.list_parties(
        db,
        current_user.company_id,
        is_customer=is_customer,
        is_vendor=is_vendor,
        parent_id=parent_id,
        search=search,
    )


@router.get(
    "/{party_id}",
    response_model=PartyRead,
    summary="Get Party by ID",
    description="Retrieve full party profile including commercial terms and child contacts.",
)
async def get_party(
    party_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PartyRead:
    """Fetch party details by UUID."""
    return await PartyService.get_party(db, current_user.company_id, party_id)


@router.patch(
    "/{party_id}",
    response_model=PartyRead,
    summary="Update Party",
    description="Update party attributes, credit limits, or hierarchy parent (with cyclic hierarchy protection).",
)
async def update_party(
    party_id: uuid.UUID,
    payload: PartyUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PartyRead:
    """Update party attributes."""
    return await PartyService.update_party(db, current_user.company_id, party_id, payload)


@router.delete(
    "/{party_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Party",
    description="Soft-delete a party record.",
)
async def delete_party(
    party_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete party by UUID."""
    await PartyService.delete_party(db, current_user.company_id, party_id)


@router.get(
    "/{party_id}/hierarchy",
    response_model=PartyHierarchyNode,
    summary="Get Party Corporate Hierarchy",
    description="Retrieve recursive descendant hierarchy tree of holding companies, subsidiaries, and branches.",
)
async def get_party_hierarchy(
    party_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PartyHierarchyNode:
    """Build full hierarchy tree for a holding party."""
    return await PartyService.get_hierarchy(db, current_user.company_id, party_id)


@router.post(
    "/{party_id}/contacts",
    response_model=PartyContactRead,
    status_code=status.HTTP_201_CREATED,
    summary="Add Party Contact",
    description="Add an individual representative contact to a party with single-primary enforcement.",
)
async def add_contact(
    party_id: uuid.UUID,
    payload: PartyContactCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PartyContactRead:
    """Add child contact to party."""
    return await PartyService.add_contact(db, current_user.company_id, party_id, payload)


@router.get(
    "/{party_id}/contacts",
    response_model=List[PartyContactRead],
    summary="List Party Contacts",
    description="List all contact persons attached to a party, ordered with primary contact first.",
)
async def list_contacts(
    party_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[PartyContactRead]:
    """Retrieve all contacts for a party."""
    return await PartyService.list_contacts(db, current_user.company_id, party_id)


@router.patch(
    "/{party_id}/contacts/{contact_id}",
    response_model=PartyContactRead,
    summary="Update Party Contact",
    description="Update an individual contact person's details or promote to primary contact.",
)
async def update_contact(
    party_id: uuid.UUID,
    contact_id: uuid.UUID,
    payload: PartyContactUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PartyContactRead:
    """Update contact attributes."""
    return await PartyService.update_contact(db, current_user.company_id, party_id, contact_id, payload)


@router.delete(
    "/{party_id}/contacts/{contact_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Party Contact",
    description="Soft-delete an individual contact person.",
)
async def delete_contact(
    party_id: uuid.UUID,
    contact_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete contact by UUID."""
    await PartyService.delete_contact(db, current_user.company_id, party_id, contact_id)
