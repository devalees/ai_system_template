"""Database model for per-module tenant configuration stores."""

from typing import Dict, Any
from sqlalchemy import String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.base_models import BaseModel


class ModuleSettings(BaseModel):
    """Stores key-value JSONB settings for a specific module within a tenant company."""
    __tablename__ = "module_settings"
    __table_args__ = (
        UniqueConstraint("company_id", "module_name", name="uq_company_module_settings"),
    )

    module_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    settings_data: Mapped[Dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
