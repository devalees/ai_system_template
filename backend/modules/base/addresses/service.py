"""Business logic and relational management service for Addresses module."""

import uuid
from typing import Optional, List, Dict, Any
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.exceptions import PlatformException
from modules.base.addresses.models import Address
from modules.base.addresses.schemas import AddressCreate, AddressUpdate, AddressRead


class AddressNotFoundException(PlatformException):
    """Raised when a requested address is not found."""
    def __init__(self, address_id: uuid.UUID):
        super().__init__(
            code="ADDRESS_NOT_FOUND",
            message=f"Address '{address_id}' not found.",
            resolution_hint="Verify the address ID or create a new address record.",
            details={"address_id": str(address_id)},
            status_code=404,
        )


class AddressService:
    """Core domain service for managing physical locations, postal addresses, and geo-coordinates."""

    @classmethod
    def _to_read_dto(cls, address: Address) -> AddressRead:
        """Helper to convert Address ORM instance to AddressRead DTO with resolved relational names."""
        return AddressRead(
            id=address.id,
            company_id=address.company_id,
            res_model=address.res_model,
            res_id=address.res_id,
            title=address.title or "",
            address_type=address.address_type,
            is_default=address.is_default,
            street1=address.street1,
            street2=address.street2,
            postal_code=address.postal_code,
            state_province=address.state_province,
            city_id=address.city_id,
            country_id=address.country_id,
            geo_lat=address.geo_lat,
            geo_lng=address.geo_lng,
            version_id=address.version_id,
            created_at=address.created_at,
            updated_at=address.updated_at,
            formatted_address=address.formatted_address,
            city_name=address.city.name if address.city else None,
            country_name=address.country.name if address.country else None,
        )

    @classmethod
    async def _unset_other_defaults(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        res_model: Optional[str],
        res_id: Optional[uuid.UUID],
        address_type: str,
        exclude_id: Optional[uuid.UUID] = None,
    ) -> None:
        """Unset is_default on any existing addresses of the same type for this target entity."""
        if not res_model or not res_id:
            return

        stmt = (
            update(Address)
            .where(
                Address.company_id == company_id,
                Address.res_model == res_model,
                Address.res_id == res_id,
                Address.address_type == address_type,
                Address.is_default.is_(True),
            )
            .values(is_default=False)
        )
        if exclude_id:
            stmt = stmt.where(Address.id != exclude_id)

        await db.execute(stmt)

    @classmethod
    async def create_address(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        payload: AddressCreate,
    ) -> AddressRead:
        """Create a new address record with optional default address management."""
        if payload.is_default and payload.res_model and payload.res_id:
            await cls._unset_other_defaults(
                db, company_id, payload.res_model, payload.res_id, payload.address_type
            )

        address = Address(
            company_id=company_id,
            res_model=payload.res_model,
            res_id=payload.res_id,
            title=payload.title,
            address_type=payload.address_type,
            is_default=payload.is_default,
            street1=payload.street1,
            street2=payload.street2,
            postal_code=payload.postal_code,
            state_province=payload.state_province,
            city_id=payload.city_id,
            country_id=payload.country_id,
            geo_lat=payload.geo_lat,
            geo_lng=payload.geo_lng,
        )
        db.add(address)
        await db.commit()
        await db.refresh(address, ["city", "country"])
        return cls._to_read_dto(address)

    @classmethod
    async def get_address(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        address_id: uuid.UUID,
    ) -> AddressRead:
        """Fetch an address by UUID."""
        stmt = (
            select(Address)
            .where(Address.company_id == company_id, Address.id == address_id)
            .options(selectinload(Address.city), selectinload(Address.country))
        )
        address = (await db.execute(stmt)).scalar_one_or_none()
        if not address:
            raise AddressNotFoundException(address_id)
        return cls._to_read_dto(address)

    @classmethod
    async def list_addresses(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        res_model: Optional[str] = None,
        res_id: Optional[uuid.UUID] = None,
        address_type: Optional[str] = None,
    ) -> List[AddressRead]:
        """Query addresses with entity and type filters."""
        stmt = (
            select(Address)
            .where(Address.company_id == company_id)
            .options(selectinload(Address.city), selectinload(Address.country))
        )
        if res_model:
            stmt = stmt.where(Address.res_model == res_model)
        if res_id:
            stmt = stmt.where(Address.res_id == res_id)
        if address_type:
            stmt = stmt.where(Address.address_type == address_type)

        stmt = stmt.order_by(Address.is_default.desc(), Address.created_at.asc())
        result = await db.execute(stmt)
        return [cls._to_read_dto(a) for a in result.scalars().all()]

    @classmethod
    async def get_default_address(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        res_model: str,
        res_id: uuid.UUID,
        address_type: Optional[str] = None,
    ) -> Optional[AddressRead]:
        """Find the designated default address for an entity, falling back to the first available."""
        stmt = (
            select(Address)
            .where(
                Address.company_id == company_id,
                Address.res_model == res_model,
                Address.res_id == res_id,
            )
            .options(selectinload(Address.city), selectinload(Address.country))
        )
        if address_type:
            stmt = stmt.where(Address.address_type == address_type)

        stmt = stmt.order_by(Address.is_default.desc(), Address.created_at.asc())
        address = (await db.execute(stmt)).scalars().first()
        return cls._to_read_dto(address) if address else None

    @classmethod
    async def update_address(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        address_id: uuid.UUID,
        payload: AddressUpdate,
    ) -> AddressRead:
        """Update address attributes and handle default flag synchronization."""
        stmt = (
            select(Address)
            .where(Address.company_id == company_id, Address.id == address_id)
            .options(selectinload(Address.city), selectinload(Address.country))
        )
        address = (await db.execute(stmt)).scalar_one_or_none()
        if not address:
            raise AddressNotFoundException(address_id)

        target_type = payload.address_type or address.address_type
        if payload.is_default is True and address.res_model and address.res_id:
            await cls._unset_other_defaults(
                db, company_id, address.res_model, address.res_id, target_type, exclude_id=address.id
            )

        update_data = payload.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(address, key, value)

        await db.commit()
        await db.refresh(address, ["city", "country"])
        return cls._to_read_dto(address)

    @classmethod
    async def delete_address(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        address_id: uuid.UUID,
    ) -> None:
        """Soft-delete an address record."""
        stmt = select(Address).where(Address.company_id == company_id, Address.id == address_id)
        address = (await db.execute(stmt)).scalar_one_or_none()
        if not address:
            raise AddressNotFoundException(address_id)

        address.soft_delete()
        await db.commit()
