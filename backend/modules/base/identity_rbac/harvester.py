"""Automated Model-Level Permission Harvester.

Inspects all registered SQLAlchemy declarative models across active modules
and automatically generates the four canonical CRUD capabilities per table:
- {module}.{resource}.create
- {module}.{resource}.read
- {module}.{resource}.update
- {module}.{resource}.delete

Idempotently upserts permissions into the database and links them to the
primary 'Super Administrators' group.
"""

import re
import uuid
import logging
from typing import List, Dict, Any, Optional, Set, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.base_models import Base
from core.kernel import kernel
from modules.base.identity_rbac.models import Permission, Group, GroupPermissionLink, Company
from modules.base.identity_rbac.flac_service import register_guarded_fields

logger = logging.getLogger("sovereign.identity_rbac.harvester")

STANDARD_ACTIONS: List[Tuple[str, str]] = [
    ("create", "Create"),
    ("read", "Read"),
    ("update", "Update"),
    ("delete", "Delete"),
]



def _to_snake_case(name: str) -> str:
    """Convert CamelCase model class name to snake_case."""
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()


def _collect_models(base_cls: Any) -> Set[Any]:
    """Recursively collect all declarative business model classes from Base."""
    collected = set()
    for sub in base_cls.__subclasses__():
        if hasattr(sub, "__tablename__") and getattr(sub, "__tablename__", None):
            # Skip internal association / link tables without distinct entity status
            if not sub.__name__.endswith("Link") and not getattr(sub, "__is_internal_link__", False):
                collected.add(sub)
        collected.update(_collect_models(sub))
    return collected


def _extract_module_and_resource(model_cls: Any) -> Tuple[str, str]:
    """Extract canonical module name and resource identifier from a model class."""
    # 1. Resource name: check __resource_name__ override, else derive from class name
    if hasattr(model_cls, "__resource_name__") and getattr(model_cls, "__resource_name__", None):
        resource = getattr(model_cls, "__resource_name__")
    else:
        resource = _to_snake_case(model_cls.__name__)

    # 2. Module name: check __module_name__ override, else extract from Python package namespace
    if hasattr(model_cls, "__module_name__") and getattr(model_cls, "__module_name__", None):
        module_name = getattr(model_cls, "__module_name__")
    else:
        parts = model_cls.__module__.split(".")
        if "modules" in parts:
            idx = parts.index("modules")
            # Expected pattern: modules.<tier>.<module_name>
            if len(parts) > idx + 2:
                module_name = parts[idx + 2]
            else:
                module_name = parts[-2]
        else:
            module_name = parts[0]

    return module_name.lower(), resource.lower()


async def harvest_model_permissions(
    db: AsyncSession,
    company_id: Optional[uuid.UUID] = None,
    auto_link_super_admin_group: bool = True,
) -> Dict[str, Any]:
    """Harvest and register all canonical CRUD capabilities across loaded models idempotently.
    
    Args:
        db: Active async database session.
        company_id: Optional company UUID. If omitted, resolves to primary tenant company.
        auto_link_super_admin_group: Whether to immediately link new permissions to 'Super Administrators'.
        
    Returns:
        Dict summarizing total models inspected, new permissions created, and super admin links.
    """
    models = _collect_models(Base)
    logger.info(f"Harvesting permissions across {len(models)} declarative business models...")

    # Fallback to primary company if company_id is None
    target_company_id = company_id
    if target_company_id is None:
        primary_comp = (await db.execute(select(Company.id).order_by(Company.created_at.asc()))).scalars().first()
        target_company_id = primary_comp

    # Query all existing permission codes
    existing_perms = (await db.execute(select(Permission.code, Permission.id))).all()
    existing_codes = {r[0]: r[1] for r in existing_perms}

    new_permissions: List[Permission] = []

    # 1. Harvest 4 CRUD actions and guarded fields for every discovered business model
    for model in sorted(models, key=lambda m: (m.__module__, m.__name__)):
        module_name, resource = _extract_module_and_resource(model)
        display_resource = resource.replace("_", " ").title()

        # 1.a Model-level CRUD permissions
        for action_code, action_title in STANDARD_ACTIONS:
            code = f"{module_name}.{resource}.{action_code}"
            if code not in existing_codes:
                perm = Permission(
                    code=code,
                    name=f"{action_title} {display_resource}",
                    module_name=module_name,
                    resource=resource,
                    action=action_code,
                    ownership_scope="GLOBAL",
                    permission_type="model",
                    company_id=target_company_id,
                )
                db.add(perm)
                new_permissions.append(perm)
                existing_codes[code] = perm.id

        # 1.b Guarded field-level permissions (FLAC)
        guarded_fields = getattr(model, "__guarded_fields__", []) or []
        if guarded_fields:
            register_guarded_fields(resource, list(guarded_fields))
            for field in guarded_fields:
                display_field = field.replace("_", " ").title()
                for f_action, f_title in [("read", "Read"), ("write", "Write")]:
                    f_code = f"{module_name}.{resource}.{field}:{f_action}"
                    if f_code not in existing_codes:
                        perm = Permission(
                            code=f_code,
                            name=f"{f_title} {display_resource} {display_field}",
                            module_name=module_name,
                            resource=resource,
                            action=f_action,
                            ownership_scope="GLOBAL",
                            permission_type="field",
                            field_name=field,
                            company_id=target_company_id,
                        )
                        db.add(perm)
                        new_permissions.append(perm)
                        existing_codes[f_code] = perm.id


    # 2. Harvest custom non-CRUD capabilities declared in module manifests
    for mod_name, manifest in kernel.manifests.items():
        custom_list = getattr(manifest, "custom_permissions", []) or []
        for cp in custom_list:
            c_action = cp.get("action", "manage").lower()
            c_resource = cp.get("resource", mod_name).lower()
            code = cp.get("code") or f"{mod_name}.{c_resource}.{c_action}".lower()
            if code not in existing_codes:
                perm = Permission(
                    code=code,
                    name=cp.get("name") or f"{c_action.capitalize()} {c_resource.replace('_', ' ').title()}",
                    module_name=mod_name.lower(),
                    resource=c_resource,
                    action=c_action,
                    ownership_scope=cp.get("ownership_scope", "GLOBAL"),
                    company_id=target_company_id,
                )
                db.add(perm)
                new_permissions.append(perm)
                existing_codes[code] = perm.id

    if new_permissions:
        await db.flush()
        logger.info(f"Created {len(new_permissions)} new model permissions in database.")

    # 3. Auto-link all active permissions to 'Super Administrators' group
    linked_count = 0
    if auto_link_super_admin_group:
        admin_group_stmt = select(Group).where(Group.name == "Super Administrators", Group.deleted_at.is_(None))
        if target_company_id:
            admin_group_stmt = admin_group_stmt.where(Group.company_id == target_company_id)
        admin_group = (await db.execute(admin_group_stmt)).scalars().first()

        if admin_group:
            # Query existing links for this group
            existing_links_stmt = select(GroupPermissionLink.permission_id).where(
                GroupPermissionLink.group_id == admin_group.id
            )
            linked_perm_ids = set((await db.execute(existing_links_stmt)).scalars().all())

            # Query all active permissions
            all_perms = (await db.execute(select(Permission).where(Permission.deleted_at.is_(None)))).scalars().all()
            for p in all_perms:
                if p.id not in linked_perm_ids:
                    db.add(
                        GroupPermissionLink(
                            group_id=admin_group.id,
                            permission_id=p.id,
                            company_id=admin_group.company_id,
                        )
                    )
                    linked_count += 1

            if linked_count > 0:
                await db.flush()
                logger.info(f"Linked {linked_count} new permissions to '{admin_group.name}' group.")

    await db.commit()

    return {
        "models_inspected": len(models),
        "new_permissions_created": len(new_permissions),
        "total_active_permissions": len(existing_codes),
        "super_admin_new_links": linked_count,
    }
