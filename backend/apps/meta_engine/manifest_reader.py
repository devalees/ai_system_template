"""
Modular App Manifest Reader and Discovery Engine.

Scans local modular app packages, parses declarative manifest.json files,
validates schema contracts, and synchronizes module definitions into the
SystemModule database registry.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from django.conf import settings
from django.core.exceptions import ValidationError

from apps.meta_engine.models import SystemModule

logger = logging.getLogger(__name__)


class ManifestValidationError(ValidationError):
    """Raised when an app manifest fails validation."""
    pass


class AppManifestReader:
    """
    Scans, reads, validates, and synchronizes modular app packages.
    """

    REQUIRED_MANIFEST_FIELDS = {"app_id", "name", "version"}

    @classmethod
    def get_modules_dir(cls) -> Path:
        """
        Return the absolute Path to the modular apps directory.
        Defaults to BASE_DIR / 'modules'.
        """
        configured_dir = getattr(settings, "MODULAR_APPS_DIR", None)
        if configured_dir:
            path = Path(configured_dir)
        else:
            path = settings.BASE_DIR / "modules"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @classmethod
    def validate_manifest(cls, manifest_data: Dict[str, Any], source_path: Optional[Path] = None) -> None:
        """
        Validate that required keys are present and correctly typed.
        """
        missing_fields = cls.REQUIRED_MANIFEST_FIELDS - manifest_data.keys()
        if missing_fields:
            src = f" in {source_path}" if source_path else ""
            raise ManifestValidationError(
                f"Manifest{src} is missing required fields: {', '.join(sorted(missing_fields))}"
            )

        app_id = manifest_data.get("app_id", "")
        if not isinstance(app_id, str) or (not app_id.isidentifier() and not app_id.replace("-", "_").isidentifier()):
            raise ManifestValidationError(
                f"Invalid 'app_id' '{app_id}'. Must be a valid alphanumeric identifier (e.g. 'crm', 'contacts_core')."
            )

    @classmethod
    def load_manifest_from_directory(cls, app_dir: Path) -> Dict[str, Any]:
        """
        Load and parse manifest.json from an application package directory.
        Supports external JSON file references for models, views, menus, automations, and reports.
        """
        manifest_file = app_dir / "manifest.json"
        if not manifest_file.exists():
            raise FileNotFoundError(f"manifest.json not found in package directory: {app_dir}")

        try:
            with open(manifest_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as exc:
            raise ManifestValidationError(f"Invalid JSON syntax in {manifest_file}: {exc}") from exc

        cls.validate_manifest(data, source_path=manifest_file)

        # Resolve relative file references if any (e.g. "models": "data/models.json")
        for section in ("models", "views", "menus", "automations", "reports"):
            val = data.get(section)
            if isinstance(val, str) and val.endswith(".json"):
                target_file = app_dir / val
                if target_file.exists():
                    try:
                        with open(target_file, "r", encoding="utf-8") as tf:
                            data[section] = json.load(tf)
                    except Exception as exc:
                        logger.warning(f"Could not load external {section} file '{target_file}': {exc}")

        return data

    @classmethod
    def discover_modules(cls) -> List[Dict[str, Any]]:
        """
        Scan the modules directory and return a list of all parsed manifest dictionaries.
        """
        modules_dir = cls.get_modules_dir()
        manifests = []

        if not modules_dir.exists():
            return manifests

        for child in sorted(modules_dir.iterdir()):
            if child.is_dir() and (child / "manifest.json").is_file():
                try:
                    manifest = cls.load_manifest_from_directory(child)
                    manifest["_package_dir"] = str(child)
                    manifests.append(manifest)
                except Exception as exc:
                    logger.error(f"Error reading modular package at '{child}': {exc}", exc_info=True)

        return manifests

    @classmethod
    def sync_discovered_modules(cls) -> List[SystemModule]:
        """
        Discover modular app packages on disk and register/update them in SystemModule.
        Preserves installed status while updating manifest metadata.
        """
        manifests = cls.discover_modules()
        synced_modules = []

        for m_data in manifests:
            app_id = m_data["app_id"]
            defaults = {
                "name": m_data.get("name", app_id.capitalize()),
                "version": str(m_data.get("version", "1.0.0")),
                "category": m_data.get("category", "General"),
                "icon": m_data.get("icon", "box"),
                "summary": m_data.get("summary", ""),
                "description": m_data.get("description", ""),
                "author": m_data.get("author", "System"),
                "website": m_data.get("website", ""),
                "license": m_data.get("license", "MIT"),
                "dependencies": m_data.get("depends", []),
                "manifest_data": m_data,
            }

            module, created = SystemModule.objects.get_or_create(
                app_id=app_id,
                defaults=defaults,
            )

            if not created:
                # Update metadata if uninstalled or available
                for key, val in defaults.items():
                    setattr(module, key, val)
                module.save()

            synced_modules.append(module)
            logger.info(f"Synchronized modular app '{app_id}' (status={module.status}).")

        return synced_modules
