"""
Safe Modular App Uninstaller and Data Policy Engine.

Safely uninstalls modular application packages with:
1. Reverse dependency validation guard (blocks uninstall if active modules depend on it).
2. Pluggable data retention policies:
   - ARCHIVE: Soft-deactivates metadata assets and hides them while keeping physical tables.
   - SNAPSHOT_BACKUP_AND_DROP: Exports table records to JSON snapshot before dropping DDL.
   - CASCADE_DROP: Purges metadata, physical tables, views, menus, and reports.
3. Clean cache eviction from DynamicModelFactory and Django app registry.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone

from apps.meta_engine.model_factory import DynamicModelFactory
from apps.meta_engine.models import (
    MetaAction,
    MetaMenu,
    MetaModel,
    MetaReport,
    MetaView,
    SystemModule,
)
from apps.meta_engine.schema_engine import DynamicSchemaEngine

logger = logging.getLogger(__name__)


class AppUninstallBlockedError(Exception):
    """Raised when an application cannot be uninstalled due to active dependents."""
    pass


class AppUninstaller:
    """
    Executes validated modular app uninstallation following specified data policies.
    """

    POLICY_ARCHIVE = "archive"
    POLICY_SNAPSHOT_BACKUP_AND_DROP = "snapshot_backup_and_drop"
    POLICY_CASCADE_DROP = "cascade_drop"

    VALID_POLICIES = {POLICY_ARCHIVE, POLICY_SNAPSHOT_BACKUP_AND_DROP, POLICY_CASCADE_DROP}

    @classmethod
    def get_dependents(cls, app_id: str) -> List[SystemModule]:
        """
        Return all currently installed modules that depend on app_id.
        """
        active_modules = SystemModule.objects.filter(status="installed").exclude(app_id=app_id)
        dependents: List[SystemModule] = []

        for mod in active_modules:
            deps = mod.dependencies or []
            if app_id in deps:
                dependents.append(mod)

        return dependents

    @classmethod
    def export_module_snapshot(cls, module: SystemModule) -> Dict[str, Any]:
        """
        Export all records from all dynamic models belonging to this module into a dictionary.
        """
        snapshot: Dict[str, Any] = {
            "app_id": module.app_id,
            "version": module.version,
            "exported_at": timezone.now().isoformat(),
            "models": {},
        }

        for meta_model in module.models.all():
            model_cls = DynamicModelFactory.get_or_create_model(meta_model)
            records = []
            if model_cls and DynamicSchemaEngine.table_exists(meta_model.table_name):
                for obj in model_cls.objects.all():
                    row_data = {}
                    for field in model_cls._meta.fields:
                        val = getattr(obj, field.name)
                        row_data[field.name] = val
                    records.append(row_data)

            snapshot["models"][meta_model.name] = {
                "label": meta_model.label,
                "table_name": meta_model.table_name,
                "count": len(records),
                "records": records,
            }

        return snapshot

    @classmethod
    def save_snapshot_to_disk(cls, module: SystemModule, snapshot_data: Dict[str, Any]) -> Path:
        """
        Write module snapshot JSON to media/backups/ directory.
        """
        backup_dir = Path(getattr(settings, "MEDIA_ROOT", settings.BASE_DIR / "media")) / "module_backups"
        backup_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = f"{module.app_id}_backup_{timestamp}.json"
        target_path = backup_dir / file_name

        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(snapshot_data, f, indent=2, cls=DjangoJSONEncoder)

        logger.info(f"Exported data snapshot for '{module.app_id}' to: {target_path}")
        return target_path

    @classmethod
    def uninstall(
        cls,
        app_id: str,
        data_policy: str = POLICY_ARCHIVE,
        force: bool = False,
    ) -> Dict[str, Any]:
        """
        Uninstall a modular application package.

        :param app_id: Identifier of the app to uninstall.
        :param data_policy: 'archive', 'snapshot_backup_and_drop', or 'cascade_drop'.
        :param force: If True, bypasses reverse dependency check (use with extreme caution).
        :return: Summary dictionary describing uninstalled components and backup details.
        """
        if data_policy not in cls.VALID_POLICIES:
            raise ValueError(f"Invalid data_policy '{data_policy}'. Must be one of: {cls.VALID_POLICIES}")

        module = SystemModule.objects.filter(app_id=app_id).first()
        if not module:
            raise ValueError(f"SystemModule with app_id '{app_id}' was not found.")

        # 1. Reverse dependency validation guard
        if not force:
            dependents = cls.get_dependents(app_id)
            if dependents:
                dependent_names = [f"'{m.name}' ({m.app_id})" for m in dependents]
                raise AppUninstallBlockedError(
                    f"Cannot uninstall module '{module.name}' ({app_id}) because the following active "
                    f"modules depend on it: {', '.join(dependent_names)}. Uninstall dependents first."
                )

        logger.info(f"Beginning uninstallation of '{app_id}' with policy '{data_policy}'...")
        result_summary: Dict[str, Any] = {
            "app_id": app_id,
            "policy": data_policy,
            "models_affected": [],
            "backup_file": None,
        }

        # 2. Execute chosen data policy
        if data_policy == cls.POLICY_SNAPSHOT_BACKUP_AND_DROP:
            snapshot = cls.export_module_snapshot(module)
            backup_file = cls.save_snapshot_to_disk(module, snapshot)
            result_summary["backup_file"] = str(backup_file)

        if data_policy in (cls.POLICY_SNAPSHOT_BACKUP_AND_DROP, cls.POLICY_CASCADE_DROP):
            # Physical purge: drop views, menus, actions, reports, models and physical tables
            # First, delete reports, menus, views, actions
            MetaReport.objects.filter(module=module).delete()
            MetaMenu.objects.filter(module=module).delete()
            MetaAction.objects.filter(module=module).delete()
            MetaView.objects.filter(module=module).delete()

            # Next, delete models (post_delete signal automatically drops PostgreSQL tables and clears factory)
            for meta_model in list(module.models.all()):
                result_summary["models_affected"].append(meta_model.name)
                meta_model.delete()

        elif data_policy == cls.POLICY_ARCHIVE:
            # Soft deactivation: keep physical tables and data, conceal from navigation & API
            for meta_model in module.models.all():
                meta_model.is_active = False
                meta_model.save()
                result_summary["models_affected"].append(meta_model.name)
                DynamicModelFactory.unregister_model(meta_model.name)

            MetaReport.objects.filter(module=module).update(is_active=False)
            MetaMenu.objects.filter(module=module).update(is_active=False)
            MetaAction.objects.filter(module=module).update(is_active=False)
            MetaView.objects.filter(module=module).update(is_active=False)

        # 3. Update module status
        module.status = "uninstalled"
        module.installed_at = None
        module.save()

        logger.info(f"Successfully uninstalled module '{app_id}' using '{data_policy}'.")
        return result_summary
