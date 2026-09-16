"""SQLAlchemy model for polymorphic Addresses and Geographic Locations."""

import uuid
from typing import Optional
from sqlalchemy import String, Boolean, Float, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.base_models import BaseModel
from modules.base.lookups.models import Country, City


class Address(BaseModel):
    """Polymorphic address entity associated with Companies, Parties, Warehouses, or Contacts."""
    __tablename__ = "addresses"

    # Polymorphic entity attachment
    res_model: Mapped[Optional[str]] = mapped_column(String(100), index=True, default=None, nullable=True)
    res_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), index=True, default=None, nullable=True)

    # Address classification
    title: Mapped[Optional[str]] = mapped_column(String(100), default="", nullable=True)
    address_type: Mapped[str] = mapped_column(
        String(30),
        default="billing",
        nullable=False,
        index=True,
    )  # "billing" | "shipping" | "branch" | "warehouse" | "contact" | "headquarters" | "other"
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)

    # Street & Postal address details
    street1: Mapped[str] = mapped_column(String(255), nullable=False)
    street2: Mapped[Optional[str]] = mapped_column(String(255), default=None, nullable=True)
    postal_code: Mapped[Optional[str]] = mapped_column(String(20), default=None, nullable=True)
    state_province: Mapped[Optional[str]] = mapped_column(String(100), default=None, nullable=True)

    # Normalized foreign keys
    city_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lookup_cities.id", ondelete="SET NULL"),
        default=None,
        nullable=True,
        index=True,
    )
    country_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lookup_countries.id", ondelete="SET NULL"),
        default=None,
        nullable=True,
        index=True,
    )

    # Geographic coordinates (GPS / mapping)
    geo_lat: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)
    geo_lng: Mapped[Optional[float]] = mapped_column(Float, default=None, nullable=True)

    # Relational loaders
    city: Mapped[Optional[City]] = relationship("City", lazy="selectin")
    country: Mapped[Optional[Country]] = relationship("Country", lazy="selectin")

    @property
    def formatted_address(self) -> str:
        """Generate human-readable standardized address string."""
        parts = [self.street1]
        if self.street2:
            parts.append(self.street2)
        if self.city:
            parts.append(self.city.name)
        elif self.state_province:
            parts.append(self.state_province)
        if self.postal_code:
            parts.append(self.postal_code)
        if self.country:
            parts.append(self.country.name)
        return ", ".join([p for p in parts if p])
