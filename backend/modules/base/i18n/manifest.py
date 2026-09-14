"""Manifest for Multi-Language & Localization Module."""

from core.manifest import ModuleManifest

MANIFEST = ModuleManifest(
    name="i18n",
    version="1.0.0",
    title="Multi-Language & Localization Engine",
    description="Multi-lingual JSONB translatable fields, Accept-Language locale resolution, RTL support, and centralized translation catalogs with Arabic as first-class citizen.",
    tier="base",
    depends_on=["identity_rbac"],
    ai_enabled=True,
    auto_install=True,
)
