"""REST API routes for Composite Addresses & Geographic Locations."""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from modules.base.identity_rbac.dependencies import get_current_user
from modules.base.identity_rbac.models import User
from modules.base.addresses.service import AddressService
from modules.base.addresses.schemas import AddressCreate, AddressUpdate, AddressRead

router = APIRouter(prefix="", tags=["Composite Addresses & Geographic Locations"])


@router.post(
    "/",
    response_model=AddressRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create Address",
    description="Create a new address record and link it polymorphically to an entity.",
)
async def create_address(
    payload: AddressCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AddressRead:
    """Create a new address record."""
    return await AddressService.create_address(db, current_user.company_id, payload)


@router.get(
    "/",
    response_model=List[AddressRead],
    summary="List Addresses",
    description="Query addresses with optional filtering by entity model, entity ID, and address type.",
)
async def list_addresses(
    res_model: Optional[str] = Query(None, description="Filter by target model name (e.g. 'Party')"),
    res_id: Optional[uuid.UUID] = Query(None, description="Filter by target record ID"),
    address_type: Optional[str] = Query(None, description="Filter by address type ('billing', 'shipping', etc.)"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[AddressRead]:
    """Retrieve filtered addresses for the active tenant company."""
    return await AddressService.list_addresses(
        db, current_user.company_id, res_model=res_model, res_id=res_id, address_type=address_type
    )


@router.get(
    "/{address_id}",
    response_model=AddressRead,
    summary="Get Address by ID",
    description="Retrieve details for a specific address record.",
)
async def get_address(
    address_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AddressRead:
    """Fetch address details by UUID."""
    return await AddressService.get_address(db, current_user.company_id, address_id)


@router.patch(
    "/{address_id}",
    response_model=AddressRead,
    summary="Update Address",
    description="Update address attributes or toggle the default address flag.",
)
async def update_address(
    address_id: uuid.UUID,
    payload: AddressUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AddressRead:
    """Update address fields."""
    return await AddressService.update_address(db, current_user.company_id, address_id, payload)


@router.delete(
    "/{address_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete Address",
    description="Soft-delete an address record.",
)
async def delete_address(
    address_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Delete address by UUID."""
    await AddressService.delete_address(db, current_user.company_id, address_id)


@router.get(
    "/entity/{res_model}/{res_id}",
    response_model=List[AddressRead],
    summary="List Entity Addresses",
    description="Retrieve all addresses linked to a specific entity record.",
)
async def list_entity_addresses(
    res_model: str,
    res_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[AddressRead]:
    """Retrieve all addresses for a specific entity."""
    return await AddressService.list_addresses(db, current_user.company_id, res_model=res_model, res_id=res_id)


@router.get(
    "/entity/{res_model}/{res_id}/default",
    response_model=Optional[AddressRead],
    summary="Get Default Entity Address",
    description="Retrieve the designated default address for an entity (optionally filtered by address type).",
)
async def get_default_entity_address(
    res_model: str,
    res_id: uuid.UUID,
    address_type: Optional[str] = Query(None, description="Address type to look for (e.g. 'billing', 'shipping')"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Optional[AddressRead]:
    """Resolve the default address for an entity."""
    return await AddressService.get_default_address(
        db, current_user.company_id, res_model=res_model, res_id=res_id, address_type=address_type
    )
