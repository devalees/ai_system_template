"""Sovereign Platform Model Extension Engine (Odoo _inherit Parity).

Enables downstream modules to extend existing base models in-place with typed SQL columns,
relationships, and business methods without directly modifying the base module source code.
Extensions are resolved in topological DAG order and migrated automatically during Kernel boot.
"""

import inspect
import logging
from typing import Dict, List, Any, Optional, Union, Type, Callable, Tuple
import sqlalchemy as sa
from sqlalchemy.orm import MappedColumn, RelationshipProperty
from sqlalchemy.dialects import postgresql

from core.base_models import BaseModel as AppBaseModel

logger = logging.getLogger("sovereign.extensions")


class ExtensionDefinition:
    """Represents a declared model extension definition."""

    def __init__(
        self,
        target_name: str,
        extension_cls: Type[Any],
        module_name: Optional[str] = None,
    ):
        self.target_name = target_name
        self.extension_cls = extension_cls
        self.module_name = module_name or extension_cls.__module__
        self.columns: Dict[str, sa.Column] = {}
        self.relationships: Dict[str, Any] = {}
        self.methods: Dict[str, Any] = {}
        self.applied: bool = False
        self._inspect_extension()

    def _inspect_extension(self) -> None:
        """Inspect extension class members to categorize columns, relationships, and methods."""
        # 1. Inspect annotations and class dict
        for attr_name, attr_val in self.extension_cls.__dict__.items():
            if attr_name.startswith("__"):
                continue

            # MappedColumn or Column
            if isinstance(attr_val, MappedColumn):
                col = attr_val.column
                if col.name is None:
                    col.name = attr_name
                if col.key is None:
                    col.key = attr_name
                if isinstance(col.type, sa.sql.sqltypes.NullType):
                    ann = getattr(self.extension_cls, "__annotations__", {}).get(attr_name)
                    inferred = self._infer_sql_type(ann)
                    if inferred is not None:
                        col.type = inferred
                self.columns[attr_name] = col
            elif isinstance(attr_val, sa.Column):
                col = attr_val
                if col.name is None:
                    col.name = attr_name
                if col.key is None:
                    col.key = attr_name
                if isinstance(col.type, sa.sql.sqltypes.NullType):
                    ann = getattr(self.extension_cls, "__annotations__", {}).get(attr_name)
                    inferred = self._infer_sql_type(ann)
                    if inferred is not None:
                        col.type = inferred
                self.columns[attr_name] = col
            elif isinstance(attr_val, RelationshipProperty):
                self.relationships[attr_name] = attr_val
            elif callable(attr_val) or isinstance(attr_val, (property, classmethod, staticmethod)):
                self.methods[attr_name] = attr_val

    @staticmethod
    def _infer_sql_type(annotation: Any) -> Optional[sa.types.TypeEngine]:
        """Infer appropriate SQLAlchemy column type from Python type annotation."""
        import typing
        import uuid as uuid_pkg
        from datetime import datetime, date
        from decimal import Decimal
        from sqlalchemy.dialects.postgresql import UUID, JSONB

        if annotation is None:
            return None

        origin = typing.get_origin(annotation)
        args = typing.get_args(annotation)

        # Handle Mapped[T] or Optional[T] / Union[T, None]
        target = annotation
        if origin is not None:
            if args:
                # If Union/Optional, pick non-None arg
                filtered = [a for a in args if a is not type(None)]
                if filtered:
                    target = filtered[0]
                    # Check if nested (e.g. Mapped[Optional[int]])
                    nested_origin = typing.get_origin(target)
                    nested_args = typing.get_args(target)
                    if nested_origin is not None and nested_args:
                        nested_filtered = [a for a in nested_args if a is not type(None)]
                        if nested_filtered:
                            target = nested_filtered[0]

        if target is int:
            return sa.Integer()
        elif target is str:
            return sa.String(255)
        elif target is float or target is Decimal:
            return sa.Numeric(18, 4)
        elif target is bool:
            return sa.Boolean()
        elif target is uuid_pkg.UUID:
            return UUID(as_uuid=True)
        elif target is datetime:
            return sa.DateTime(timezone=True)
        elif target is date:
            return sa.Date()
        elif target is dict or target is list:
            return JSONB()

        return sa.String(255)

        logger.debug(
            f"Inspected extension '{self.extension_cls.__name__}' for '{self.target_name}': "
            f"{len(self.columns)} columns, {len(self.relationships)} relationships, {len(self.methods)} methods"
        )


class ModelExtensionRegistry:
    """Central registry managing in-place model extensions across all platform modules."""

    _instance: Optional["ModelExtensionRegistry"] = None

    def __new__(cls) -> "ModelExtensionRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.extensions: List[ExtensionDefinition] = []
            cls._instance.applied_columns: Dict[str, List[Tuple[str, sa.Column]]] = {}
        return cls._instance

    def register(
        self, target: Union[str, Type[Any]]
    ) -> Callable[[Type[Any]], Type[Any]]:
        """Decorator to register a model extension class.
        
        Usage:
            @extend_model("parties.Party")
            class PartyAccountingExtension:
                credit_limit: Mapped[float] = mapped_column(default=0.0)
                def get_limit(self):
                    return self.credit_limit
        """
        def decorator(extension_cls: Type[Any]) -> Type[Any]:
            target_name = target if isinstance(target, str) else target.__name__
            ext_def = ExtensionDefinition(
                target_name=target_name,
                extension_cls=extension_cls,
            )
            self.extensions.append(ext_def)
            logger.info(
                f"Registered model extension '{extension_cls.__name__}' targeting '{target_name}'"
            )
            return extension_cls

        return decorator

    def clear(self) -> None:
        """Reset registry (primarily for testing purposes)."""
        self.extensions.clear()
        self.applied_columns.clear()

    def resolve_target_model(self, target_name: str) -> Optional[Any]:
        """Resolve a target model class from registry mappers by class name, table name, or module.model."""
        clean_target = target_name.strip().lower()

        # Check if dot notation like "parties.Party"
        target_model_name = clean_target.split(".")[-1]

        for mapper in AppBaseModel.registry.mappers:
            cls = mapper.class_
            cls_name = cls.__name__.lower()
            tbl_name = getattr(cls, "__tablename__", "").lower()

            if cls_name == clean_target or cls_name == target_model_name:
                return cls
            if tbl_name == clean_target or tbl_name == target_model_name:
                return cls

        return None

    def apply_extensions(self) -> int:
        """Apply all pending registered extensions to their target SQLAlchemy models.
        
        Returns the total number of extensions successfully applied.
        """
        applied_count = 0

        for ext in self.extensions:
            if ext.applied:
                continue

            target_cls = self.resolve_target_model(ext.target_name)
            if target_cls is None:
                logger.warning(
                    f"Deferred extension '{ext.extension_cls.__name__}': "
                    f"target model '{ext.target_name}' not yet loaded in registry"
                )
                continue

            table = getattr(target_cls, "__table__", None)
            mapper = getattr(target_cls, "__mapper__", None)

            if table is None or mapper is None:
                logger.error(
                    f"Target class '{target_cls.__name__}' is missing __table__ or __mapper__"
                )
                continue

            tbl_name = table.name
            if tbl_name not in self.applied_columns:
                self.applied_columns[tbl_name] = []

            # 1. Apply Columns
            for col_name, col in ext.columns.items():
                if col_name not in table.columns:
                    table.append_column(col)
                    mapper.add_property(col_name, col)
                    self.applied_columns[tbl_name].append((col_name, col))
                    logger.debug(f"Injected column '{col_name}' into model '{target_cls.__name__}' ({tbl_name})")
                else:
                    logger.debug(f"Column '{col_name}' already exists on '{tbl_name}'")

            # 2. Apply Relationships
            for rel_name, rel in ext.relationships.items():
                if rel_name not in mapper.relationships:
                    mapper.add_property(rel_name, rel)
                    logger.debug(f"Injected relationship '{rel_name}' into model '{target_cls.__name__}'")

            # 3. Apply Methods and Properties
            for method_name, method in ext.methods.items():
                setattr(target_cls, method_name, method)
                logger.debug(f"Injected method/property '{method_name}' into model '{target_cls.__name__}'")

            ext.applied = True
            applied_count += 1
            logger.info(
                f"Successfully applied extension '{ext.extension_cls.__name__}' to '{target_cls.__name__}' "
                f"({len(ext.columns)} cols, {len(ext.relationships)} rels, {len(ext.methods)} methods)"
            )

        return applied_count

    def generate_column_ddl(self, table_name: str, col_name: str, col: sa.Column) -> str:
        """Generate safe, idempotent PostgreSQL DDL for a single extension column."""
        dialect = postgresql.dialect()
        type_str = col.type.compile(dialect=dialect)

        # Default clause
        default_clause = ""
        if col.server_default is not None:
            default_clause = f" DEFAULT {col.server_default.arg}"
        elif col.default is not None and getattr(col.default, "is_scalar", False):
            val = col.default.arg
            if isinstance(val, bool):
                val_str = "TRUE" if val else "FALSE"
            elif isinstance(val, (int, float)):
                val_str = str(val)
            elif isinstance(val, str):
                val_str = f"'{val}'"
            else:
                val_str = f"'{str(val)}'"
            default_clause = f" DEFAULT {val_str}"

        # Nullability clause: in extensions, columns are nullable by default to avoid failing on existing data
        null_clause = " NOT NULL" if (not col.nullable and default_clause) else " NULL"

        # Foreign Key clause
        fk_clause = ""
        if col.foreign_keys:
            fk = list(col.foreign_keys)[0]
            target_table = fk.column.table.name if hasattr(fk.column, "table") and fk.column.table is not None else fk._column_tokens[0]
            target_col = fk.column.name if hasattr(fk.column, "name") else "id"
            fk_clause = f" REFERENCES {target_table}({target_col})"
            if fk.ondelete:
                fk_clause += f" ON DELETE {fk.ondelete}"

        return f"ALTER TABLE public.{table_name} ADD COLUMN IF NOT EXISTS {col_name} {type_str}{default_clause}{null_clause}{fk_clause};"

    async def execute_migrations(self, conn: Any) -> List[str]:
        """Execute programmatic DDL migrations for all applied extension columns.
        
        Checks information_schema.columns to only alter when necessary.
        Returns the list of executed DDL statements.
        """
        executed: List[str] = []

        if not self.applied_columns:
            return executed

        # Query existing columns in public schema
        result = await conn.execute(sa.text("""
            SELECT table_name, column_name 
            FROM information_schema.columns 
            WHERE table_schema = 'public';
        """))
        existing_cols = {(row[0], row[1]) for row in result.fetchall()}

        for table_name, cols in self.applied_columns.items():
            for col_name, col in cols:
                if (table_name, col_name) not in existing_cols:
                    ddl = self.generate_column_ddl(table_name, col_name, col)
                    try:
                        await conn.execute(sa.text(ddl))
                        executed.append(ddl)
                        logger.info(f"Executed extension migration DDL: {ddl}")
                    except Exception as exc:
                        logger.error(f"Failed executing extension DDL '{ddl}': {exc}", exc_info=True)
                        raise

        return executed


# Global Registry Instance and Decorator Export
model_extension_registry = ModelExtensionRegistry()
extend_model = model_extension_registry.register
