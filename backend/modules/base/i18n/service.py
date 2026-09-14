"""Service layer for multi-lingual translation catalogs, bilingual field resolution, and locale metadata."""

import uuid
import logging
from typing import Dict, Any, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.context import get_active_locale
from modules.base.i18n.models import TranslationTerm
from modules.base.i18n.schemas import LocaleInfo, CatalogResponse

logger = logging.getLogger("sovereign.i18n.service")

# Core supported languages with native RTL support
SUPPORTED_LOCALES = [
    LocaleInfo(code="en", name="English", native_name="English", direction="ltr", is_default=True),
    LocaleInfo(code="ar", name="Arabic", native_name="العربية", direction="rtl", is_default=False),
]

# Baseline system UI translation seed dictionary
DEFAULT_DICTIONARY: Dict[str, Dict[str, str]] = {
    "Save": {"en": "Save", "ar": "حفظ"},
    "Cancel": {"en": "Cancel", "ar": "إلغاء"},
    "Delete": {"en": "Delete", "ar": "حذف"},
    "Edit": {"en": "Edit", "ar": "تعديل"},
    "Search": {"en": "Search", "ar": "بحث"},
    "Create": {"en": "Create", "ar": "إنشاء"},
    "Settings": {"en": "Settings", "ar": "الإعدادات"},
    "Notifications": {"en": "Notifications", "ar": "الإشعارات"},
    "Dashboard": {"en": "Dashboard", "ar": "لوحة التحكم"},
    "Status": {"en": "Status", "ar": "الحالة"},
    "Back": {"en": "Back", "ar": "رجوع"},
    "Submit": {"en": "Submit", "ar": "إرسال"},
    "Invoices": {"en": "Invoices", "ar": "الفواتير"},
    "Customers": {"en": "Customers", "ar": "العملاء"},
    "Products": {"en": "Products", "ar": "المنتجات"},
}


class I18nService:
    """Service providing catalog compilation, live term lookup, and localized field resolution."""

    @classmethod
    def get_supported_locales(cls) -> List[LocaleInfo]:
        """Return list of supported system languages with text direction."""
        return SUPPORTED_LOCALES

    @classmethod
    def resolve_field(cls, field_val: Any, preferred_locale: Optional[str] = None) -> str:
        """Resolve a bilingual JSONB field (e.g. {'en': 'Name', 'ar': 'الاسم'}) to a string."""
        if isinstance(field_val, str):
            return field_val
        if not isinstance(field_val, dict):
            return str(field_val or "")

        locale = preferred_locale or get_active_locale() or "en"
        # 1. Exact locale match
        if locale in field_val and field_val[locale]:
            return str(field_val[locale])
        # 2. English fallback
        if "en" in field_val and field_val["en"]:
            return str(field_val["en"])
        # 3. Arabic fallback
        if "ar" in field_val and field_val["ar"]:
            return str(field_val["ar"])
        # 4. First available non-empty value
        for val in field_val.values():
            if val:
                return str(val)
        return ""

    @classmethod
    async def translate_term(
        cls,
        db: AsyncSession,
        source_text: str,
        target_locale: str,
        company_id: uuid.UUID,
        module_name: Optional[str] = None,
    ) -> str:
        """Translate a single term checking tenant-specific terms, then fallback dictionary."""
        # 1. Check custom tenant terms in database
        stmt = select(TranslationTerm).where(
            TranslationTerm.company_id == company_id,
            TranslationTerm.source_text == source_text,
            TranslationTerm.is_active == True,
        )
        if module_name:
            stmt = stmt.where(TranslationTerm.module_name.in_([module_name, "all"]))

        res = await db.execute(stmt)
        custom_term = res.scalar_one_or_none()
        if custom_term and target_locale in custom_term.translations:
            return custom_term.translations[target_locale]

        # 2. Check default system dictionary
        if source_text in DEFAULT_DICTIONARY:
            return DEFAULT_DICTIONARY[source_text].get(target_locale, source_text)

        # 3. Fallback to original text
        return source_text

    @classmethod
    async def get_catalog(
        cls,
        db: AsyncSession,
        target_locale: str,
        company_id: uuid.UUID,
        module_name: Optional[str] = None,
    ) -> CatalogResponse:
        """Compile complete active dictionary of terms for the target language."""
        compiled_terms: Dict[str, str] = {}

        # 1. Load baseline system defaults
        for src, trans_map in DEFAULT_DICTIONARY.items():
            compiled_terms[src] = trans_map.get(target_locale, src)

        # 2. Overlay tenant-specific overrides from database
        stmt = select(TranslationTerm).where(
            TranslationTerm.company_id == company_id,
            TranslationTerm.is_active == True,
        )
        if module_name:
            stmt = stmt.where(TranslationTerm.module_name.in_([module_name, "all"]))

        res = await db.execute(stmt)
        terms = res.scalars().all()
        for term in terms:
            if target_locale in term.translations:
                compiled_terms[term.source_text] = term.translations[target_locale]

        direction = "rtl" if target_locale == "ar" else "ltr"
        return CatalogResponse(
            locale=target_locale,
            direction=direction,
            total_terms=len(compiled_terms),
            terms=compiled_terms,
        )
