"""Database models for the Universal Sequence & Legal Auto-Numbering Engine."""

import uuid
from typing import Optional
from datetime import datetime
from sqlalchemy import String, Integer, Boolean, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from core.base_models import BaseModel


class Sequence(BaseModel):
    """Universal Sequence definition governing legal document numbering and series."""
    __tablename__ = "sequences"
    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_company_sequence_code"),
    )

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    prefix: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    suffix: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    padding: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    current_number: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    step: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    reset_period: Mapped[str] = mapped_column(String(20), default="never", nullable=False)  # never | yearly | monthly | daily
    last_reset_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
