"""
Modular App Package Installer Engine.

Executes declarative application package installation:
1. Resolves prerequisite dependencies in topological order.
2. Ingests dynamic models and non-relational fields (Pass 1).
3. Ingests cross-model relational links and foreign keys (Pass 2).
4. Ingests UI views (forms, lists, kanbans).
5. Ingests actions and navigation menus.
6. Ingests automations and printable PDF/HTML reports.
7. Compiles live in-memory Django models and marks module installed.
"""

import logging
from typing import Any, Dict, List, Optional

from django.db import transaction
from django.utils import timezone

from apps.meta_engine.dependency_resolver import DependencyResolver
from apps.meta_engine.manifest_reader import AppManifestReader
from apps.meta_engine.model_factory import DynamicModelFactory
from apps.meta_engine.models import (
    MetaAction,
    MetaField,
    MetaMenu,
    MetaModel,
    MetaReport,
    MetaView,
    SystemModule,
)

logger = logging.getLogger(__name__)


class AppInstallationError(Exception):
    """Raised when modular app installation encounters a failure."""
    pass


class AppInstaller:
    """
    Executes multi-pass declarative installation of modular applications.
    """

    @classmethod
    def install(cls, app_id: str, manifest_data: Optional[Dict[str, Any]] = None) -> List[SystemModule]:
        """
        Install an application package and all its prerequisite dependencies.

        :param app_id: Target application identifier (e.g. 'crm', 'contacts').
        :param manifest_data: Optional in-memory manifest dict. If omitted,
                              retrieved from SystemModule or scanned from disk.
        :return: List of all SystemModule instances installed during this operation.
        """
        # 1. Sync manifests from disk if needed
        AppManifestReader.sync_discovered_modules()

        # If custom manifest_data provided, ensure SystemModule exists and has it
        target_mod = SystemModule.objects.filter(app_id=app_id).first()
        if not target_mod and manifest_data:
            target_mod = SystemModule.objects.create(
                app_id=app_id,
                name=manifest_data.get("name", app_id.capitalize()),
                version=manifest_data.get("version", "1.0.0"),
                dependencies=manifest_data.get("depends", []),
                manifest_data=manifest_data,
            )
        elif target_mod and manifest_data:
            target_mod.manifest_data = manifest_data
            target_mod.dependencies = manifest_data.get("depends", target_mod.dependencies)
            target_mod.save()

        # 2. Determine topological installation order
        install_sequence = DependencyResolver.resolve_install_order([app_id])
        logger.info(f"Topological installation order for '{app_id}': {install_sequence}")

        installed_modules: List[SystemModule] = []

        # 3. Install each module in sequence
        for current_app_id in install_sequence:
            module_record = SystemModule.objects.filter(app_id=current_app_id).first()
            if not module_record:
                raise AppInstallationError(f"Module '{current_app_id}' record not found in database.")

            m_data = module_record.manifest_data or {}
            if not m_data and manifest_data and current_app_id == app_id:
                m_data = manifest_data

            cls._install_single_module(module_record, m_data)
            installed_modules.append(module_record)

        return installed_modules

    @classmethod
    def _install_single_module(cls, module: SystemModule, manifest: Dict[str, Any]) -> None:
        """
        Execute atomic declarative ingestion for a single module package.
        """
        logger.info(f"Installing module '{module.app_id}' v{module.version}...")

        try:
            models_data = manifest.get("models", [])
            views_data = manifest.get("views", [])
            actions_data = manifest.get("actions", [])
            menus_data = manifest.get("menus", [])
            reports_data = manifest.get("reports", [])

            created_meta_models: List[MetaModel] = []

            # --- PASS 1: Create MetaModels and non-relational MetaFields ---
            for m_spec in models_data:
                model_name = m_spec["name"].strip().lower().replace(" ", "_")
                meta_model, _ = MetaModel.objects.update_or_create(
                    name=model_name,
                    defaults={
                        "label": m_spec.get("label", model_name.capitalize()),
                        "label_plural": m_spec.get("label_plural", ""),
                        "app_label": m_spec.get("app_label", module.app_id),
                        "description": m_spec.get("description", ""),
                        "is_system": m_spec.get("is_system", False),
                        "is_auditable": m_spec.get("is_auditable", True),
                        "is_soft_delete": m_spec.get("is_soft_delete", False),
                        "ordering_field": m_spec.get("ordering_field", "-created_at"),
                        "module": module,
                    },
                )
                created_meta_models.append(meta_model)

                # Ingest scalar / non-relational fields
                for f_spec in m_spec.get("fields", []):
                    f_type = f_spec.get("field_type", "char")
                    if f_type in ("foreign_key", "many_to_many"):
                        continue  # Defer to Pass 2

                    f_name = f_spec["name"].strip().lower().replace(" ", "_")
                    MetaField.objects.update_or_create(
                        model=meta_model,
                        name=f_name,
                        defaults={
                            "label": f_spec.get("label", f_name.replace("_", " ").title()),
                            "field_type": f_type,
                            "max_length": f_spec.get("max_length", 255),
                            "max_digits": f_spec.get("max_digits", 12),
                            "decimal_places": f_spec.get("decimal_places", 2),
                            "required": f_spec.get("required", False),
                            "unique": f_spec.get("unique", False),
                            "index": f_spec.get("index", False),
                            "default_value": str(f_spec.get("default", "")) if f_spec.get("default") is not None else "",
                            "choices": f_spec.get("choices", []),
                            "help_text": f_spec.get("help_text", ""),
                            "sequence": f_spec.get("sequence", 10),
                            "is_system": f_spec.get("is_system", False),
                            "is_readonly": f_spec.get("is_readonly", False),
                        },
                    )

            # --- PASS 2: Ingest Relational Fields (Foreign Keys) ---
            for m_spec in models_data:
                model_name = m_spec["name"].strip().lower().replace(" ", "_")
                meta_model = MetaModel.objects.filter(name=model_name).first()
                if not meta_model:
                    continue

                for f_spec in m_spec.get("fields", []):
                    f_type = f_spec.get("field_type")
                    if f_type != "foreign_key":
                        continue

                    f_name = f_spec["name"].strip().lower().replace(" ", "_")
                    target_model_name = f_spec.get("fk_target_model")
                    target_app_model = f_spec.get("fk_target_app_model")

                    fk_target = None
                    if target_model_name:
                        fk_target = MetaModel.objects.filter(name=target_model_name).first()

                    MetaField.objects.update_or_create(
                        model=meta_model,
                        name=f_name,
                        defaults={
                            "label": f_spec.get("label", f_name.replace("_", " ").title()),
                            "field_type": "foreign_key",
                            "required": f_spec.get("required", False),
                            "unique": f_spec.get("unique", False),
                            "index": True,
                            "fk_target_model": fk_target,
                            "fk_target_app_model": target_app_model or "",
                            "on_delete_behavior": f_spec.get("on_delete", "SET_NULL"),
                            "help_text": f_spec.get("help_text", ""),
                            "sequence": f_spec.get("sequence", 10),
                        },
                    )

            # --- PASS 3: Ingest Views ---
            for v_spec in views_data:
                target_model_name = v_spec.get("model")
                meta_model = MetaModel.objects.filter(name=target_model_name).first()
                if not meta_model:
                    logger.warning(f"Skipping view '{v_spec.get('name')}': Target model '{target_model_name}' not found.")
                    continue

                MetaView.objects.update_or_create(
                    model=meta_model,
                    name=v_spec["name"],
                    defaults={
                        "view_type": v_spec.get("view_type", "form"),
                        "is_default": v_spec.get("is_default", False),
                        "layout_schema": v_spec.get("layout_schema", {}),
                        "module": module,
                    },
                )

            # --- PASS 4: Ingest Actions ---
            for a_spec in actions_data:
                action_name = a_spec["name"]
                target_model = None
                if a_spec.get("model"):
                    target_model = MetaModel.objects.filter(name=a_spec["model"]).first()

                target_view = None
                if a_spec.get("view"):
                    target_view = MetaView.objects.filter(name=a_spec["view"]).first()

                MetaAction.objects.update_or_create(
                    name=action_name,
                    defaults={
                        "action_type": a_spec.get("action_type", "window"),
                        "target_model": target_model,
                        "target_view": target_view,
                        "domain_filter": a_spec.get("domain_filter", {}),
                        "context": a_spec.get("context", {}),
                        "server_handler": a_spec.get("server_handler", ""),
                        "module": module,
                    },
                )

            # --- PASS 5: Ingest Menus ---
            for menu_spec in menus_data:
                parent_menu = None
                if menu_spec.get("parent"):
                    parent_menu = MetaMenu.objects.filter(name=menu_spec["parent"]).first()

                action = None
                if menu_spec.get("action"):
                    action = MetaAction.objects.filter(name=menu_spec["action"]).first()

                MetaMenu.objects.update_or_create(
                    name=menu_spec["name"],
                    app_label=menu_spec.get("app_label", module.app_id),
                    defaults={
                        "icon": menu_spec.get("icon", "folder"),
                        "sequence": menu_spec.get("sequence", 10),
                        "parent": parent_menu,
                        "action": action,
                        "module": module,
                    },
                )

            # --- PASS 6: Ingest Printable Reports ---
            for rep_spec in reports_data:
                target_model_name = rep_spec.get("model")
                meta_model = MetaModel.objects.filter(name=target_model_name).first()
                if not meta_model:
                    logger.warning(f"Skipping report '{rep_spec.get('name')}': Target model '{target_model_name}' not found.")
                    continue

                slug = rep_spec.get("slug") or f"{module.app_id}_{meta_model.name}_report"
                MetaReport.objects.update_or_create(
                    slug=slug,
                    defaults={
                        "model": meta_model,
                        "name": rep_spec["name"],
                        "report_type": rep_spec.get("report_type", "pdf"),
                        "paper_format": rep_spec.get("paper_format", "A4"),
                        "orientation": rep_spec.get("orientation", "portrait"),
                        "template_dsl": rep_spec.get("template_dsl", ""),
                        "layout_schema": rep_spec.get("layout_schema", {}),
                        "is_default": rep_spec.get("is_default", False),
                        "module": module,
                    },
                )

            # --- PASS 7: Compile dynamic models in memory ---
            for meta_model in created_meta_models:
                try:
                    DynamicModelFactory.get_or_create_model(meta_model, force_reload=True)
                except Exception as exc:
                    logger.warning(f"Failed to compile model '{meta_model.name}' during installation: {exc}")

            # Mark module installed
            module.status = "installed"
            module.installed_at = timezone.now()
            module.save()
            logger.info(f"Module '{module.app_id}' installed successfully.")

        except Exception as exc:
            module.status = "error"
            module.save()
            logger.error(f"Installation of module '{module.app_id}' failed: {exc}", exc_info=True)
            raise AppInstallationError(f"Failed to install module '{module.app_id}': {exc}") from exc
