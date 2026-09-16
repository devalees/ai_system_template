"""Domain service for Unified Party management, contacts, and corporate hierarchies."""

import uuid
from typing import Optional, List, Dict, Any, Set
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.exceptions import PlatformException
from modules.base.parties.models import Party, PartyContact
from modules.base.parties.schemas import (
    PartyCreate,
    PartyUpdate,
    PartyRead,
    PartyContactCreate,
    PartyContactUpdate,
    PartyContactRead,
    PartyHierarchyNode,
)


class PartyNotFoundException(PlatformException):
    """Raised when a requested party does not exist."""
    def __init__(self, party_id: uuid.UUID):
        super().__init__(
            code="PARTY_NOT_FOUND",
            message=f"Party '{party_id}' not found.",
            resolution_hint="Verify the party UUID or register a new party.",
            details={"party_id": str(party_id)},
            status_code=404,
        )


class ContactNotFoundException(PlatformException):
    """Raised when a requested contact does not exist."""
    def __init__(self, contact_id: uuid.UUID):
        super().__init__(
            code="CONTACT_NOT_FOUND",
            message=f"Party contact '{contact_id}' not found.",
            resolution_hint="Verify the contact ID or add a new contact.",
            details={"contact_id": str(contact_id)},
            status_code=404,
        )


class PartyService:
    """Core domain service for Unified Partner and Contact operations."""

    @classmethod
    def _to_party_dto(cls, party: Party) -> PartyRead:
        """Helper to transform Party ORM instance into enriched PartyRead DTO."""
        contacts_dto = [
            PartyContactRead(
                id=c.id,
                company_id=c.company_id,
                party_id=c.party_id,
                name=c.name,
                job_title=c.job_title or "",
                email=c.email,
                phone=c.phone,
                mobile=c.mobile,
                is_primary=c.is_primary,
                version_id=c.version_id,
                created_at=c.created_at,
                updated_at=c.updated_at,
            )
            for c in (party.contacts or [])
        ]

        return PartyRead(
            id=party.id,
            company_id=party.company_id,
            name=party.name,
            legal_name=party.legal_name,
            is_company=party.is_company,
            parent_id=party.parent_id,
            is_customer=party.is_customer,
            is_vendor=party.is_vendor,
            is_employee=party.is_employee,
            tax_id=party.tax_id,
            commercial_reg_no=party.commercial_reg_no,
            currency_id=party.currency_id,
            credit_limit=party.credit_limit,
            linked_company_id=party.linked_company_id,
            email=party.email,
            phone=party.phone,
            website=party.website,
            parent_name=party.parent.name if party.parent else None,
            currency_code=party.currency.code if party.currency else None,
            linked_company_name=party.linked_company.name if party.linked_company else None,
            contacts=contacts_dto,
            version_id=party.version_id,
            created_at=party.created_at,
            updated_at=party.updated_at,
        )

    @classmethod
    async def _assert_no_cyclic_hierarchy(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        party_id: Optional[uuid.UUID],
        target_parent_id: Optional[uuid.UUID],
    ) -> None:
        """Detect and prevent circular parent-child loops in organizational holding structures."""
        if not target_parent_id or not party_id:
            return

        if party_id == target_parent_id:
            raise PlatformException(
                code="SELF_PARENT_NOT_ALLOWED",
                message="A party cannot be assigned as its own parent.",
                resolution_hint="Select a distinct parent entity or leave parent_id empty.",
                status_code=400,
            )

        visited: Set[uuid.UUID] = {party_id}
        curr_id: Optional[uuid.UUID] = target_parent_id

        while curr_id is not None:
            if curr_id in visited:
                raise PlatformException(
                    code="CYCLIC_HIERARCHY_DETECTED",
                    message="Circular hierarchy detected: cannot set parent relationship.",
                    resolution_hint="Ensure the parent party is higher in the hierarchy tree.",
                    details={"party_id": str(party_id), "parent_id": str(target_parent_id)},
                    status_code=400,
                )
            visited.add(curr_id)
            stmt = select(Party.parent_id).where(Party.company_id == company_id, Party.id == curr_id)
            curr_id = (await db.execute(stmt)).scalar_one_or_none()

    @classmethod
    async def create_party(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        payload: PartyCreate,
    ) -> PartyRead:
        """Create a new unified party with optional contacts and hierarchy validation."""
        if payload.parent_id:
            await cls._assert_no_cyclic_hierarchy(db, company_id, None, payload.parent_id)

        party = Party(
            company_id=company_id,
            name=payload.name,
            legal_name=payload.legal_name,
            is_company=payload.is_company,
            parent_id=payload.parent_id,
            is_customer=payload.is_customer,
            is_vendor=payload.is_vendor,
            is_employee=payload.is_employee,
            tax_id=payload.tax_id,
            commercial_reg_no=payload.commercial_reg_no,
            currency_id=payload.currency_id,
            credit_limit=payload.credit_limit,
            linked_company_id=payload.linked_company_id,
            email=payload.email,
            phone=payload.phone,
            website=payload.website,
        )
        db.add(party)
        await db.flush()

        has_primary = False
        for c in payload.contacts:
            is_prim = c.is_primary and not has_primary
            if is_prim:
                has_primary = True
            contact = PartyContact(
                company_id=company_id,
                party_id=party.id,
                name=c.name,
                job_title=c.job_title or "",
                email=c.email,
                phone=c.phone,
                mobile=c.mobile,
                is_primary=is_prim,
            )
            db.add(contact)

        await db.commit()
        return await cls.get_party(db, company_id, party.id)

    @classmethod
    async def get_party(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        party_id: uuid.UUID,
    ) -> PartyRead:
        """Fetch a specific party by UUID."""
        stmt = (
            select(Party)
            .where(Party.company_id == company_id, Party.id == party_id)
            .options(
                selectinload(Party.contacts),
                selectinload(Party.parent),
                selectinload(Party.currency),
                selectinload(Party.linked_company),
            )
        )
        party = (await db.execute(stmt)).scalar_one_or_none()
        if not party:
            raise PartyNotFoundException(party_id)
        return cls._to_party_dto(party)

    @classmethod
    async def list_parties(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        is_customer: Optional[bool] = None,
        is_vendor: Optional[bool] = None,
        parent_id: Optional[uuid.UUID] = None,
        search: Optional[str] = None,
    ) -> List[PartyRead]:
        """Query parties with role filters and search."""
        stmt = (
            select(Party)
            .where(Party.company_id == company_id)
            .options(
                selectinload(Party.contacts),
                selectinload(Party.parent),
                selectinload(Party.currency),
                selectinload(Party.linked_company),
            )
        )
        if is_customer is not None:
            stmt = stmt.where(Party.is_customer == is_customer)
        if is_vendor is not None:
            stmt = stmt.where(Party.is_vendor == is_vendor)
        if parent_id is not None:
            stmt = stmt.where(Party.parent_id == parent_id)
        if search:
            stmt = stmt.where(Party.name.ilike(f"%{search}%"))

        stmt = stmt.order_by(Party.name.asc())
        result = await db.execute(stmt)
        return [cls._to_party_dto(p) for p in result.scalars().all()]

    @classmethod
    async def update_party(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        party_id: uuid.UUID,
        payload: PartyUpdate,
    ) -> PartyRead:
        """Update party fields and guard against cyclic hierarchies."""
        stmt = (
            select(Party)
            .where(Party.company_id == company_id, Party.id == party_id)
            .options(
                selectinload(Party.contacts),
                selectinload(Party.parent),
                selectinload(Party.currency),
                selectinload(Party.linked_company),
            )
        )
        party = (await db.execute(stmt)).scalar_one_or_none()
        if not party:
            raise PartyNotFoundException(party_id)

        if payload.parent_id is not None:
            await cls._assert_no_cyclic_hierarchy(db, company_id, party_id, payload.parent_id)

        update_dict = payload.model_dump(exclude_unset=True)
        for key, val in update_dict.items():
            setattr(party, key, val)

        await db.commit()
        return await cls.get_party(db, company_id, party.id)

    @classmethod
    async def delete_party(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        party_id: uuid.UUID,
    ) -> None:
        """Soft-delete a party record."""
        stmt = select(Party).where(Party.company_id == company_id, Party.id == party_id)
        party = (await db.execute(stmt)).scalar_one_or_none()
        if not party:
            raise PartyNotFoundException(party_id)

        party.soft_delete()
        await db.commit()

    @classmethod
    async def get_hierarchy(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        party_id: uuid.UUID,
    ) -> PartyHierarchyNode:
        """Build full recursive descendant hierarchy tree for a holding party."""
        root = await cls.get_party(db, company_id, party_id)

        async def _build_tree(node_id: uuid.UUID, node_name: str, is_comp: bool, is_cust: bool, is_vend: bool) -> PartyHierarchyNode:
            stmt = select(Party).where(Party.company_id == company_id, Party.parent_id == node_id).order_by(Party.name.asc())
            children = (await db.execute(stmt)).scalars().all()
            child_nodes = []
            for child in children:
                child_nodes.append(
                    await _build_tree(child.id, child.name, child.is_company, child.is_customer, child.is_vendor)
                )
            return PartyHierarchyNode(
                id=node_id,
                name=node_name,
                is_company=is_comp,
                is_customer=is_cust,
                is_vendor=is_vend,
                subsidiaries=child_nodes,
            )

        return await _build_tree(root.id, root.name, root.is_company, root.is_customer, root.is_vendor)

    @classmethod
    async def add_contact(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        party_id: uuid.UUID,
        payload: PartyContactCreate,
    ) -> PartyContactRead:
        """Add a child contact to a party with single-primary enforcement."""
        # Ensure party exists
        await cls.get_party(db, company_id, party_id)

        if payload.is_primary:
            # Unset existing primary contacts
            await db.execute(
                update(PartyContact)
                .where(PartyContact.company_id == company_id, PartyContact.party_id == party_id)
                .values(is_primary=False)
            )

        contact = PartyContact(
            company_id=company_id,
            party_id=party_id,
            name=payload.name,
            job_title=payload.job_title or "",
            email=payload.email,
            phone=payload.phone,
            mobile=payload.mobile,
            is_primary=payload.is_primary,
        )
        db.add(contact)
        await db.commit()
        await db.refresh(contact)

        return PartyContactRead(
            id=contact.id,
            company_id=contact.company_id,
            party_id=contact.party_id,
            name=contact.name,
            job_title=contact.job_title or "",
            email=contact.email,
            phone=contact.phone,
            mobile=contact.mobile,
            is_primary=contact.is_primary,
            version_id=contact.version_id,
            created_at=contact.created_at,
            updated_at=contact.updated_at,
        )

    @classmethod
    async def list_contacts(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        party_id: uuid.UUID,
    ) -> List[PartyContactRead]:
        """List all contacts attached to a party."""
        await cls.get_party(db, company_id, party_id)
        stmt = (
            select(PartyContact)
            .where(PartyContact.company_id == company_id, PartyContact.party_id == party_id)
            .order_by(PartyContact.is_primary.desc(), PartyContact.name.asc())
        )
        contacts = (await db.execute(stmt)).scalars().all()
        return [
            PartyContactRead(
                id=c.id,
                company_id=c.company_id,
                party_id=c.party_id,
                name=c.name,
                job_title=c.job_title or "",
                email=c.email,
                phone=c.phone,
                mobile=c.mobile,
                is_primary=c.is_primary,
                version_id=c.version_id,
                created_at=c.created_at,
                updated_at=c.updated_at,
            )
            for c in contacts
        ]

    @classmethod
    async def update_contact(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        party_id: uuid.UUID,
        contact_id: uuid.UUID,
        payload: PartyContactUpdate,
    ) -> PartyContactRead:
        """Update a specific contact person."""
        stmt = select(PartyContact).where(
            PartyContact.company_id == company_id,
            PartyContact.party_id == party_id,
            PartyContact.id == contact_id,
        )
        contact = (await db.execute(stmt)).scalar_one_or_none()
        if not contact:
            raise ContactNotFoundException(contact_id)

        if payload.is_primary is True:
            await db.execute(
                update(PartyContact)
                .where(
                    PartyContact.company_id == company_id,
                    PartyContact.party_id == party_id,
                    PartyContact.id != contact_id,
                )
                .values(is_primary=False)
            )

        update_dict = payload.model_dump(exclude_unset=True)
        for key, val in update_dict.items():
            setattr(contact, key, val)

        await db.commit()
        await db.refresh(contact)
        return PartyContactRead(
            id=contact.id,
            company_id=contact.company_id,
            party_id=contact.party_id,
            name=contact.name,
            job_title=contact.job_title or "",
            email=contact.email,
            phone=contact.phone,
            mobile=contact.mobile,
            is_primary=contact.is_primary,
            version_id=contact.version_id,
            created_at=contact.created_at,
            updated_at=contact.updated_at,
        )

    @classmethod
    async def delete_contact(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        party_id: uuid.UUID,
        contact_id: uuid.UUID,
    ) -> None:
        """Soft-delete a party contact."""
        stmt = select(PartyContact).where(
            PartyContact.company_id == company_id,
            PartyContact.party_id == party_id,
            PartyContact.id == contact_id,
        )
        contact = (await db.execute(stmt)).scalar_one_or_none()
        if not contact:
            raise ContactNotFoundException(contact_id)

        contact.soft_delete()
        await db.commit()
