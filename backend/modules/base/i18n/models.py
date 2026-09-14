"""Database models for translation catalogs and localized terms."""

from typing import Optional, Dict
from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.base_models import BaseModel


class TranslationTerm(BaseModel):
    """Normalized multi-lingual term with language mappings."""
    __tablename__ = "translation_terms"

    source_text: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    module_name: Mapped[str] = mapped_column(String(100), default="all", nullable=False, index=True)
    translations: Mapped[Dict[str, str]] = mapped_column(JSONB, default=dict, nullable=False)
    context_hint: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
