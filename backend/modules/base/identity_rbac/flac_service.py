"""Field-Level Access Control (FLAC) and Effective Permissions Service.

Calculates effective permission matrices (Union of Roles + Direct Grants - Direct Revocations)
and enforces field-level egress pruning (read) and ingress mutation guards (write).
"""

import uuid
import logging
from typing import Dict, Any, List, Set, Optional, Union
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.base_models import Base
from core.exceptions import PermissionDeniedException
from modules.base.identity_rbac.models import (
    User,
    Group,
    Permission,
    UserGroupLink,
    GroupPermissionLink,
    UserPermissionLink,
)
from modules.base.identity_rbac.schemas import (
    UserEffectivePermissionsResponse,
    PermissionRead,
)

logger = logging.getLogger("sovereign.identity_rbac.flac")

# Central registry of guarded / sensitive fields per resource
# Populated via model __guarded_fields__ or registered dynamically
_GUARDED_FIELDS_MAP: Dict[str, Set[str]] = {}


def register_guarded_fields(resource_name: str, fields: List[str]) -> None:
    """Register guarded/sensitive fields for a business resource."""
    normalized = resource_name.lower()
    if normalized not in _GUARDED_FIELDS_MAP:
        _GUARDED_FIELDS_MAP[normalized] = set()
    _GUARDED_FIELDS_MAP[normalized].update(fields)


def get_guarded_fields(resource_name: str) -> Set[str]:
    """Retrieve the set of guarded field names for a specific resource."""
    return _GUARDED_FIELDS_MAP.get(resource_name.lower(), set())


def discover_model_guarded_fields(base_cls: Any = Base) -> None:
    """Inspect all declarative models inheriting from Base for __guarded_fields__ attribute."""
    for sub in base_cls.__subclasses__():
        if hasattr(sub, "__tablename__") and getattr(sub, "__tablename__", None):
            res_name = getattr(sub, "__resource_name__", sub.__name__.lower())
            guarded = getattr(sub, "__guarded_fields__", None)
            if guarded and isinstance(guarded, (list, tuple, set)):
                register_guarded_fields(res_name, list(guarded))


class FLACService:
    """Enterprise Field-Level Access Control and Effective Permissions Engine."""

    @staticmethod
    async def get_effective_permissions(
        user: User,
        db: AsyncSession,
    ) -> UserEffectivePermissionsResponse:
        """Compute the full effective permissions matrix for a user or AI bot.
        
        Formula:
            Effective = (Assigned Roles / Groups Permissions) + (Direct Grants) - (Direct Revocations)
        """
        # 1. Superuser short-circuit: all permissions are granted
        if user.is_superuser:
            all_perms = (await db.execute(
                select(Permission).where(Permission.deleted_at.is_(None)).execution_options(ignore_tenant=True)
            )).scalars().all()
            model_codes = [p.code for p in all_perms if p.permission_type == "model"]
            all_codes = [p.code for p in all_perms]
            
            # Build wildcard field permissions
            field_perms_map: Dict[str, Dict[str, List[str]]] = {}
            for p in all_perms:
                if p.permission_type == "field" and p.field_name:
                    if p.resource not in field_perms_map:
                        field_perms_map[p.resource] = {"read": [], "write": []}
                    action_key = "write" if p.action in ("update", "create", "delete", "write") else "read"
                    if p.field_name not in field_perms_map[p.resource][action_key]:
                        field_perms_map[p.resource][action_key].append(p.field_name)

            return UserEffectivePermissionsResponse(
                user_id=user.id,
                username=user.username,
                user_type=user.user_type,
                is_superuser=True,
                assigned_roles=[{"id": "superadmin", "name": "Super Administrators", "group_type": "role"}],
                direct_overrides=[],
                model_permissions=model_codes,
                field_permissions=field_perms_map,
                all_effective_codes=all_codes,
            )

        # 2. Fetch assigned groups / roles
        stmt_groups = (
            select(Group.id, Group.name, Group.group_type)
            .join(UserGroupLink, UserGroupLink.group_id == Group.id)
            .where(UserGroupLink.user_id == user.id, Group.deleted_at.is_(None))
            .execution_options(ignore_tenant=True)
        )
        group_rows = (await db.execute(stmt_groups)).all()
        assigned_roles = [
            {"id": str(r[0]), "name": r[1], "group_type": r[2]}
            for r in group_rows
        ]
        group_ids = [r[0] for r in group_rows]

        # 3. Query group permissions
        group_perms_by_code: Dict[str, Permission] = {}
        if group_ids:
            stmt_gperms = (
                select(Permission)
                .join(GroupPermissionLink, GroupPermissionLink.permission_id == Permission.id)
                .where(GroupPermissionLink.group_id.in_(group_ids), Permission.deleted_at.is_(None))
                .execution_options(ignore_tenant=True)
            )
            for p in (await db.execute(stmt_gperms)).scalars().all():
                group_perms_by_code[p.code] = p

        # 4. Query direct user overrides
        stmt_direct = (
            select(UserPermissionLink, Permission)
            .join(Permission, Permission.id == UserPermissionLink.permission_id)
            .where(UserPermissionLink.user_id == user.id, Permission.deleted_at.is_(None))
            .execution_options(ignore_tenant=True)
        )
        direct_rows = (await db.execute(stmt_direct)).all()
        direct_overrides_summary: List[Dict[str, Any]] = []

        effective_perms_by_code: Dict[str, Permission] = dict(group_perms_by_code)

        for link, perm in direct_rows:
            direct_overrides_summary.append({
                "permission_id": str(perm.id),
                "code": perm.code,
                "name": perm.name,
                "is_granted": link.is_granted,
                "permission_type": perm.permission_type,
                "field_name": perm.field_name,
            })
            if link.is_granted:
                # Direct additive grant
                effective_perms_by_code[perm.code] = perm
            else:
                # Direct explicit revocation
                effective_perms_by_code.pop(perm.code, None)

        # 5. Structure categorized output
        model_permissions: List[str] = []
        field_permissions_map: Dict[str, Dict[str, List[str]]] = {}

        for code, perm in effective_perms_by_code.items():
            if perm.permission_type == "field" and perm.field_name:
                if perm.resource not in field_permissions_map:
                    field_permissions_map[perm.resource] = {"read": [], "write": []}
                action_key = "write" if perm.action in ("update", "create", "delete", "write") else "read"
                if perm.field_name not in field_permissions_map[perm.resource][action_key]:
                    field_permissions_map[perm.resource][action_key].append(perm.field_name)
            else:
                model_permissions.append(code)

        return UserEffectivePermissionsResponse(
            user_id=user.id,
            username=user.username,
            user_type=user.user_type,
            is_superuser=False,
            assigned_roles=assigned_roles,
            direct_overrides=direct_overrides_summary,
            model_permissions=sorted(model_permissions),
            field_permissions=field_permissions_map,
            all_effective_codes=sorted(list(effective_perms_by_code.keys())),
        )

    @staticmethod
    async def has_permission(
        user: User,
        permission_code: str,
        db: AsyncSession,
    ) -> bool:
        """Fast permission verification checking superuser, direct overrides, and group roles."""
        if user.is_superuser:
            return True

        # 1. Check direct user override (grants take precedence, revocations take precedence)
        stmt_direct = (
            select(UserPermissionLink.is_granted)
            .join(Permission, Permission.id == UserPermissionLink.permission_id)
            .where(UserPermissionLink.user_id == user.id, Permission.code == permission_code)
            .execution_options(ignore_tenant=True)
        )
        direct_grant = (await db.execute(stmt_direct)).scalar_one_or_none()
        if direct_grant is not None:
            return bool(direct_grant)

        # 2. Check group/role permissions
        stmt_group = (
            select(Permission.id)
            .join(GroupPermissionLink, GroupPermissionLink.permission_id == Permission.id)
            .join(UserGroupLink, UserGroupLink.group_id == GroupPermissionLink.group_id)
            .where(UserGroupLink.user_id == user.id, Permission.code == permission_code)
            .execution_options(ignore_tenant=True)
        )
        has_perm = (await db.execute(stmt_group)).scalar_one_or_none()
        return has_perm is not None


    @staticmethod
    def sanitize_read_fields(
        record_dict: Dict[str, Any],
        resource_name: str,
        effective_codes: Set[str],
        is_superuser: bool = False,
        module_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Egress filter: removes or masks guarded fields if caller lacks {module}.{resource}.{field}:read."""
        if is_superuser:
            return record_dict

        guarded = get_guarded_fields(resource_name)
        if not guarded:
            return record_dict

        sanitized = dict(record_dict)
        for field in guarded:
            if field in sanitized:
                # Check permission codes (supports with or without module prefix)
                has_read = False
                for code in effective_codes:
                    if f".{resource_name}.{field}:read" in code or code.endswith(f"{resource_name}.{field}:read") or code == f"{resource_name}.{field}:read":
                        has_read = True
                        break
                    if module_name and code == f"{module_name}.{resource_name}.{field}:read":
                        has_read = True
                        break

                if not has_read:
                    # Prune the field from output payload
                    sanitized.pop(field, None)

        return sanitized

    @staticmethod
    def validate_write_fields(
        payload_dict: Dict[str, Any],
        resource_name: str,
        effective_codes: Set[str],
        is_superuser: bool = False,
        module_name: Optional[str] = None,
    ) -> None:
        """Ingress guard: rejects mutation if payload contains guarded fields without write capability."""
        if is_superuser:
            return

        guarded = get_guarded_fields(resource_name)
        if not guarded:
            return

        for field in guarded:
            if field in payload_dict:
                has_write = False
                for code in effective_codes:
                    if f".{resource_name}.{field}:write" in code or code.endswith(f"{resource_name}.{field}:write") or code == f"{resource_name}.{field}:write":
                        has_write = True
                        break
                    if module_name and code == f"{module_name}.{resource_name}.{field}:write":
                        has_write = True
                        break

                if not has_write:
                    raise PermissionDeniedException(
                        action=f"write to guarded field '{field}'",
                        resource=resource_name,
                    )
