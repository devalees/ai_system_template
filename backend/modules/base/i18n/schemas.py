"""Pydantic schemas for multi-language translation terms, catalogs, and locale metadata."""

import uuid
from datetime import datetime
from typing import Optional, Dict, List
from pydantic import BaseModel, Field, ConfigDict


class LocaleInfo(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "code": "ar",
                "name": "Arabic",
                "native_name": "العربية",
                "direction": "rtl",
                "is_default": False
            }
        }
    )

    code: str = Field(..., description="ISO 639-1 language code (e.g., en, ar)")
    name: str = Field(..., description="Language English display name")
    native_name: str = Field(..., description="Native script language name")
    direction: str = Field("ltr", description="Text layout direction: ltr or rtl")
    is_default: bool = Field(False, description="Default fallback system locale")


class TranslationTermRead(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "t0000000-0000-0000-0000-000000000001",
                "company_id": "a0000000-0000-0000-0000-000000000001",
                "source_text": "Save",
                "module_name": "core",
                "translations": {"en": "Save", "ar": "حفظ"},
                "context_hint": "Form submit button",
                "is_active": True,
                "created_at": "2026-09-14T02:50:00Z"
            }
        }
    )

    id: uuid.UUID
    company_id: uuid.UUID
    source_text: str
    module_name: str
    translations: Dict[str, str]
    context_hint: Optional[str]
    is_active: bool
    created_at: datetime


class TranslationTermCreate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "source_text": "Invoices",
                "module_name": "accounting",
                "translations": {"en": "Invoices", "ar": "الفواتير"},
                "context_hint": "Navigation menu item"
            }
        }
    )

    source_text: str = Field(..., max_length=255, description="English / base source term string")
    module_name: str = Field("all", max_length=100, description="Application module namespace")
    translations: Dict[str, str] = Field(default_factory=dict, description="Locale to translated string map")
    context_hint: Optional[str] = Field(None, max_length=255, description="Disambiguation hint for translators")


class TranslationTermUpdate(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "translations": {"en": "Tax Invoices", "ar": "الفواتير الضريبية"}
            }
        }
    )

    source_text: Optional[str] = Field(None, max_length=255)
    module_name: Optional[str] = Field(None, max_length=100)
    translations: Optional[Dict[str, str]] = None
    context_hint: Optional[str] = None
    is_active: Optional[bool] = None


class TranslateRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "text": "Submit Payment",
                "target_locale": "ar",
                "module_name": "accounting"
            }
        }
    )

    text: str = Field(..., description="Source string to translate")
    target_locale: str = Field("ar", description="Target ISO language code")
    module_name: Optional[str] = Field(None, description="Optional module context")


class TranslateResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "source_text": "Submit Payment",
                "translated_text": "إرسال الدفعة",
                "locale": "ar"
            }
        }
    )

    source_text: str
    translated_text: str
    locale: str


class CatalogResponse(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "locale": "ar",
                "direction": "rtl",
                "total_terms": 24,
                "terms": {
                    "Save": "حفظ",
                    "Cancel": "إلغاء",
                    "Delete": "حذف",
                    "Edit": "تعديل",
                    "Invoices": "الفواتير"
                }
            }
        }
    )

    locale: str
    direction: str
    total_terms: int
    terms: Dict[str, str]
