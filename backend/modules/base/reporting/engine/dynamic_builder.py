"""Dynamic ORM query compiler and aggregation engine for ad-hoc and user-defined reports."""

import uuid
import datetime
import logging
from typing import Dict, Any, List, Optional
import sqlalchemy as sa
from sqlalchemy.orm import Mapper
from sqlalchemy.ext.asyncio import AsyncSession

from modules.base.automated_actions.introspection import find_model_class, _humanize_name, _resolve_type_name
from modules.base.automated_actions.engine.evaluator import ASTConditionEvaluator
from modules.base.reporting.registry import ReportDataResult

logger = logging.getLogger("sovereign.reporting.dynamic_builder")


class DynamicReportQueryEngine:
    """Compiles dynamic report specifications into SQLAlchemy queries and computes aggregates."""

    @classmethod
    async def execute_query(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        target_model: str,
        selected_fields: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None,
        group_by: Optional[List[str]] = None,
        aggregations: Optional[Dict[str, str]] = None,
        order_by: Optional[List[str]] = None,
        limit: int = 1000,
    ) -> ReportDataResult:
        """Execute a dynamic aggregation or tabular query against any registered model."""
        model_cls = find_model_class(target_model)
        if not model_cls:
            raise ValueError(f"Target model '{target_model}' not found in registry")

        mapper: Mapper = sa.inspect(model_cls)
        valid_cols = {col.name: col for col in mapper.columns}

        # 1. Base query with tenancy and soft-delete scoping
        stmt = sa.select()
        where_clauses = []

        if hasattr(model_cls, "company_id"):
            where_clauses.append(getattr(model_cls, "company_id") == company_id)

        if hasattr(model_cls, "deleted_at"):
            where_clauses.append(getattr(model_cls, "deleted_at").is_(None))

        columns_meta: List[Dict[str, Any]] = []
        is_grouped = bool(group_by and aggregations)

        # 2. Grouped Aggregation vs Flat Tabular Selection
        if is_grouped:
            select_exprs = []

            # Group By Columns
            for col_name in (group_by or []):
                if col_name in valid_cols:
                    col_obj = valid_cols[col_name]
                    select_exprs.append(col_obj.label(col_name))
                    columns_meta.append({
                        "name": col_name,
                        "title": _humanize_name(col_name),
                        "type": _resolve_type_name(col_obj.type),
                        "is_group": True,
                    })

            # Aggregate Columns
            for field_name, agg_func in (aggregations or {}).items():
                if field_name in valid_cols:
                    col_obj = valid_cols[field_name]
                    agg_name = f"{field_name}_{agg_func}"
                    func_lower = agg_func.lower()

                    if func_lower == "count":
                        expr = sa.func.count(col_obj).label(agg_name)
                        col_type = "integer"
                    elif func_lower == "sum":
                        expr = sa.func.sum(col_obj).label(agg_name)
                        col_type = "float"
                    elif func_lower == "avg":
                        expr = sa.func.avg(col_obj).label(agg_name)
                        col_type = "float"
                    elif func_lower == "min":
                        expr = sa.func.min(col_obj).label(agg_name)
                        col_type = _resolve_type_name(col_obj.type)
                    elif func_lower == "max":
                        expr = sa.func.max(col_obj).label(agg_name)
                        col_type = _resolve_type_name(col_obj.type)
                    else:
                        continue

                    select_exprs.append(expr)
                    columns_meta.append({
                        "name": agg_name,
                        "title": f"{_humanize_name(field_name)} ({agg_func.upper()})",
                        "type": col_type,
                        "is_aggregate": True,
                    })

            stmt = sa.select(*select_exprs)
            for clause in where_clauses:
                stmt = stmt.where(clause)

            group_cols = [valid_cols[c] for c in (group_by or []) if c in valid_cols]
            if group_cols:
                stmt = stmt.group_by(*group_cols)

        else:
            # Flat tabular query
            target_field_names = selected_fields or list(valid_cols.keys())
            select_cols = []
            for col_name in target_field_names:
                if col_name in valid_cols:
                    col_obj = valid_cols[col_name]
                    select_cols.append(col_obj)
                    columns_meta.append({
                        "name": col_name,
                        "title": _humanize_name(col_name),
                        "type": _resolve_type_name(col_obj.type),
                    })

            stmt = sa.select(*select_cols)
            for clause in where_clauses:
                stmt = stmt.where(clause)

        # 3. Order By
        if order_by:
            for ord_str in order_by:
                parts = ord_str.strip().split()
                col_name = parts[0]
                is_desc = len(parts) > 1 and parts[1].lower() == "desc"

                # Check if col_name in selected columns or model columns
                if col_name in valid_cols:
                    col_obj = valid_cols[col_name]
                    stmt = stmt.order_by(col_obj.desc() if is_desc else col_obj.asc())
        elif hasattr(model_cls, "created_at") and not is_grouped:
            stmt = stmt.order_by(getattr(model_cls, "created_at").desc())

        stmt = stmt.limit(limit)

        # 4. Execute Query
        result = await db.execute(stmt)
        raw_rows = result.all()

        rows: List[Dict[str, Any]] = []
        grand_totals: Dict[str, Any] = {}

        for raw in raw_rows:
            row_dict: Dict[str, Any] = {}
            if hasattr(raw, "_mapping"):
                for col_meta in columns_meta:
                    key = col_meta["name"]
                    val = raw._mapping.get(key)
                    if isinstance(val, (datetime.datetime, datetime.date)):
                        val = val.isoformat()
                    elif isinstance(val, uuid.UUID):
                        val = str(val)
                    row_dict[key] = val
            rows.append(row_dict)

        # 5. Apply AST Condition filtering if provided on flat queries
        if filters and not is_grouped:
            rows = [r for r in rows if ASTConditionEvaluator.evaluate(filters, r)]

        # 6. Calculate Grand Totals across numeric columns
        for col_meta in columns_meta:
            c_name = col_meta["name"]
            c_type = col_meta["type"]
            if c_type in ("integer", "float"):
                numeric_vals = [r[c_name] for r in rows if r.get(c_name) is not None and isinstance(r.get(c_name), (int, float))]
                if numeric_vals:
                    grand_totals[c_name] = round(sum(numeric_vals), 4)

        return ReportDataResult(
            report_code=f"dynamic.{target_model.lower()}",
            report_name=f"{_humanize_name(target_model)} Dynamic Report",
            target_model=target_model,
            columns=columns_meta,
            rows=rows,
            aggregates=grand_totals,
            total_rows=len(rows),
            generated_at=datetime.datetime.utcnow().isoformat(),
        )
