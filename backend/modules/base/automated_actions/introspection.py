"""ORM Model and Field introspection service for Automated Actions and Dynamic Query Engines."""

import re
import uuid
import logging
from typing import List, Dict, Any, Optional, Set
import sqlalchemy as sa
from sqlalchemy.orm import Mapper
from sqlalchemy.dialects.postgresql import UUID, JSONB

from core.base_models import BaseModel as AppBaseModel

logger = logging.getLogger("sovereign.automated_actions.introspection")

# Fields automatically managed by the system or action execution context
AUTO_MANAGED_FIELDS: Set[str] = {
    "id",
    "company_id",
    "created_at",
    "updated_at",
    "deleted_at",
    "created_by_id",
    "updated_by_id",
    "deleted_by_id",
    "is_deleted",
    "is_archived",
    "archived_at",
}

READ_ONLY_FIELDS: Set[str] = {
    "id",
    "created_at",
    "updated_at",
    "deleted_at",
    "created_by_id",
    "updated_by_id",
    "deleted_by_id",
}


def _humanize_name(name: str) -> str:
    """Convert PascalCase or snake_case string to human-readable title."""
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", name)
    return s.replace("_", " ").title()


def _resolve_type_name(col_type: Any) -> str:
    """Map SQLAlchemy column type to unified JSON schema type string."""
    if isinstance(col_type, (sa.String, sa.Text)):
        return "string"
    elif isinstance(col_type, (sa.Integer, sa.BigInteger, sa.SmallInteger)):
        return "integer"
    elif isinstance(col_type, (sa.Float, sa.Numeric)):
        return "float"
    elif isinstance(col_type, sa.Boolean):
        return "boolean"
    elif isinstance(col_type, (UUID, sa.Uuid)):
        return "uuid"
    elif isinstance(col_type, (sa.DateTime, sa.TIMESTAMP)):
        return "datetime"
    elif isinstance(col_type, sa.Date):
        return "date"
    elif isinstance(col_type, (JSONB, sa.JSON)):
        return "json"
    elif isinstance(col_type, sa.Enum):
        return "enum"
    return "string"


def get_registered_models() -> List[Dict[str, Any]]:
    """Inspect all registered SQLAlchemy models and return catalog metadata."""
    models: List[Dict[str, Any]] = []

    for mapper in AppBaseModel.registry.mappers:
        cls = mapper.class_
        model_name = cls.__name__
        table_name = getattr(cls, "__tablename__", "")

        # Skip transient link / join tables if not directly business models
        if model_name.endswith("Link") and "link" in table_name:
            continue

        # Extract module name from package path (e.g. modules.base.documents.models -> documents)
        parts = cls.__module__.split(".")
        module_name = parts[2] if len(parts) >= 3 else parts[0]

        models.append({
            "model_name": model_name,
            "module_name": module_name,
            "table_name": table_name,
            "title": _humanize_name(model_name),
            "description": (cls.__doc__ or "").strip().split("\n")[0] if cls.__doc__ else None,
            "is_tenant_scoped": hasattr(cls, "company_id"),
            "fields_count": len(mapper.columns),
        })

    models.sort(key=lambda x: (x["module_name"], x["model_name"]))
    return models


def find_model_class(model_name: str) -> Optional[Any]:
    """Find mapper class by name (case-insensitive) or table name."""
    clean_target = model_name.strip().lower()
    for mapper in AppBaseModel.registry.mappers:
        cls = mapper.class_
        if cls.__name__.lower() == clean_target:
            return cls
        if getattr(cls, "__tablename__", "").lower() == clean_target:
            return cls
    return None


def get_model_fields(model_name: str, depth: int = 1) -> Optional[Dict[str, Any]]:
    """Return comprehensive field and relationship metadata for a specific model."""
    cls = find_model_class(model_name)
    if not cls:
        return None

    mapper: Mapper = sa.inspect(cls)
    fields: List[Dict[str, Any]] = []

    for col in mapper.columns:
        type_str = _resolve_type_name(col.type)
        is_required = not col.nullable and col.default is None and col.server_default is None and not col.primary_key
        user_required = is_required and col.name not in AUTO_MANAGED_FIELDS

        # Inspect foreign keys
        is_relation = bool(col.foreign_keys)
        foreign_table = None
        foreign_column = None
        foreign_model = None

        if is_relation:
            fk = next(iter(col.foreign_keys))
            foreign_table = fk.column.table.name
            foreign_column = fk.column.name
            target_cls = find_model_class(foreign_table)
            if target_cls:
                foreign_model = target_cls.__name__

        # Extract enum choices if present
        choices = None
        if isinstance(col.type, sa.Enum) and col.type.enums:
            choices = [{"value": val, "label": _humanize_name(val)} for val in col.type.enums]

        fields.append({
            "name": col.name,
            "title": _humanize_name(col.name),
            "type": type_str,
            "nullable": col.nullable,
            "required": user_required,
            "read_only": col.name in READ_ONLY_FIELDS or col.primary_key,
            "is_relation": is_relation,
            "foreign_model": foreign_model,
            "foreign_table": foreign_table,
            "foreign_column": foreign_column,
            "choices": choices,
            "default": str(col.default.arg) if col.default and hasattr(col.default, "arg") else None,
        })

    # Inspect relationships (M:1, 1:M, M:M)
    relationships: List[Dict[str, Any]] = []
    for rel_name, rel in mapper.relationships.items():
        if rel_name.startswith("_"):
            continue

        target_class = getattr(rel.entity, "class_", None) or getattr(rel.mapper, "class_", None)
        target_model_name = target_class.__name__ if target_class else str(rel.target)
        fk_cols = [c.name for c in rel.local_columns] if hasattr(rel, "local_columns") else []

        nested_fields = None
        if depth > 1 and target_class:
            nested_spec = get_model_fields(target_model_name, depth=depth - 1)
            if nested_spec:
                nested_fields = nested_spec.get("fields")

        relationships.append({
            "name": rel_name,
            "title": _humanize_name(rel_name),
            "target_model": target_model_name,
            "direction": rel.direction.name if hasattr(rel, "direction") else "MANYTOONE",
            "is_collection": bool(rel.uselist),
            "foreign_keys": fk_cols,
            "fields": nested_fields,
        })

    parts = cls.__module__.split(".")
    module_name = parts[2] if len(parts) >= 3 else parts[0]

    return {
        "model_name": cls.__name__,
        "module_name": module_name,
        "table_name": getattr(cls, "__tablename__", ""),
        "title": _humanize_name(cls.__name__),
        "description": (cls.__doc__ or "").strip().split("\n")[0] if cls.__doc__ else None,
        "fields": fields,
        "relationships": relationships,
    }


def resolve_field_path(model_cls: Any, field_path: str) -> Optional[Dict[str, Any]]:
    """Resolve a single or dot-separated field path against an ORM model and return target metadata."""
    if not field_path:
        return None

    segments = field_path.strip().split(".")
    current_cls = model_cls
    rel_chain: List[str] = []

    for segment in segments[:-1]:
        mapper: Mapper = sa.inspect(current_cls)
        if segment not in mapper.relationships:
            return None
        rel = mapper.relationships[segment]
        target_cls = getattr(rel.entity, "class_", None) or getattr(rel.mapper, "class_", None)
        if not target_cls:
            return None
        current_cls = target_cls
        rel_chain.append(segment)

    terminal_field = segments[-1]
    terminal_mapper: Mapper = sa.inspect(current_cls)
    if terminal_field not in terminal_mapper.columns:
        return None

    col = terminal_mapper.columns[terminal_field]
    return {
        "field_path": field_path,
        "terminal_column": col,
        "terminal_model": current_cls,
        "column_name": terminal_field,
        "type": _resolve_type_name(col.type),
        "title": " > ".join([_humanize_name(s) for s in segments]),
        "relationship_chain": rel_chain,
    }



def validate_create_record_config(model_name: str, values: Dict[str, Any]) -> List[str]:
    """Pre-flight validation for create_record action configuration. Returns list of error messages."""
    errors: List[str] = []
    cls = find_model_class(model_name)
    if not cls:
        return [f"Target model '{model_name}' is not registered in the system."]

    mapper: Mapper = sa.inspect(cls)
    valid_cols = {col.name: col for col in mapper.columns}

    # 1. Verify all provided values correspond to valid model columns
    for key in values.keys():
        if key not in valid_cols:
            errors.append(f"Field '{key}' does not exist on model '{cls.__name__}'.")

    # 2. Verify all strictly required fields are supplied (or templated)
    for col_name, col in valid_cols.items():
        if col_name in AUTO_MANAGED_FIELDS:
            continue

        is_strictly_required = not col.nullable and col.default is None and col.server_default is None and not col.primary_key
        if is_strictly_required and (col_name not in values or values[col_name] is None):
            errors.append(f"Required field '{col_name}' on model '{cls.__name__}' is missing in action values.")

    return errors


def validate_update_record_config(target_model: str, fields: Dict[str, Any]) -> List[str]:
    """Pre-flight validation for update_record action configuration. Returns list of error messages."""
    errors: List[str] = []
    cls = find_model_class(target_model)
    if not cls:
        return [f"Target model '{target_model}' is not registered in the system."]

    mapper: Mapper = sa.inspect(cls)
    valid_cols = {col.name: col for col in mapper.columns}

    for key in fields.keys():
        if key not in valid_cols:
            errors.append(f"Field '{key}' does not exist on model '{cls.__name__}'.")
        elif key in READ_ONLY_FIELDS or valid_cols[key].primary_key:
            errors.append(f"Field '{key}' on model '{cls.__name__}' is read-only and cannot be updated.")

    return errors
