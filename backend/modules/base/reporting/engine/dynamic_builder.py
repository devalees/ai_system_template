"""Dynamic ORM query compiler, relational path resolver, and document aggregation engine."""

import uuid
import datetime
import logging
from typing import Dict, Any, List, Optional, Tuple
import sqlalchemy as sa
from sqlalchemy.orm import Mapper, aliased
from sqlalchemy.ext.asyncio import AsyncSession

from modules.base.automated_actions.introspection import find_model_class, _humanize_name, _resolve_type_name
from modules.base.automated_actions.engine.evaluator import ASTConditionEvaluator
from modules.base.reporting.registry import ReportDataResult

logger = logging.getLogger("sovereign.reporting.dynamic_builder")


class DynamicReportQueryEngine:
    """Compiles dynamic report specifications into SQLAlchemy queries and computes aggregates."""

    @classmethod
    def _resolve_column_expression(
        cls,
        root_model: Any,
        field_path: str,
        joins_registry: Dict[str, Any],
        stmt: sa.sql.Select,
    ) -> Tuple[Optional[sa.sql.ColumnElement], Optional[str], Optional[str], sa.sql.Select]:
        """
        Resolve a direct or dot-separated field path (e.g. 'country.name' or 'parent.parent.code')
        into an aliased column expression and append any necessary LEFT OUTER JOINs to the SELECT statement.
        """
        clean_path = field_path.strip()
        segments = clean_path.split(".")

        # Case 1: Direct Column on root model
        if len(segments) == 1:
            col_name = segments[0]
            root_mapper: Mapper = sa.inspect(root_model)
            if col_name in root_mapper.columns:
                col_obj = getattr(root_model, col_name)
                col_type = _resolve_type_name(col_obj.type)
                title = _humanize_name(col_name)
                return col_obj.label(clean_path), col_type, title, stmt
            return None, None, None, stmt

        # Case 2: Multi-Hop Relational Path (e.g. country.currency.code)
        current_entity = root_model
        path_acc = ""

        for seg in segments[:-1]:
            path_acc = f"{path_acc}.{seg}" if path_acc else seg

            if path_acc in joins_registry:
                current_entity = joins_registry[path_acc]
            else:
                cur_insp = sa.inspect(current_entity)
                cur_relationships = cur_insp.relationships if hasattr(cur_insp, "relationships") else cur_insp.mapper.relationships
                if seg not in cur_relationships:
                    cls_name = getattr(cur_insp, "class_", None).__name__ if hasattr(cur_insp, "class_") else str(current_entity)
                    logger.warning(f"Relationship '{seg}' not found on model '{cls_name}' for path '{clean_path}'")
                    return None, None, None, stmt

                rel = cur_relationships[seg]
                target_cls = getattr(rel.entity, "class_", None) or getattr(rel.mapper, "class_", None)
                if not target_cls:
                    return None, None, None, stmt

                safe_alias_name = "rel_" + path_acc.replace(".", "_")
                alias_entity = aliased(target_cls, name=safe_alias_name)

                # Outer join target entity via relationship
                rel_attr = getattr(current_entity, seg)
                stmt = stmt.outerjoin(rel_attr.of_type(alias_entity))

                joins_registry[path_acc] = alias_entity
                current_entity = alias_entity

        # Terminal column on the last joined entity
        term_col_name = segments[-1]
        term_insp = sa.inspect(current_entity)
        term_columns = term_insp.columns if hasattr(term_insp, "columns") else term_insp.mapper.columns
        if term_col_name in term_columns:
            col_obj = getattr(current_entity, term_col_name)
            col_type = _resolve_type_name(col_obj.type)
            title = " > ".join([_humanize_name(s) for s in segments])
            return col_obj.label(clean_path), col_type, title, stmt

        return None, None, None, stmt

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
        """Execute a dynamic aggregation or tabular query against any registered model with dot-notation joins."""
        model_cls = find_model_class(target_model)
        if not model_cls:
            raise ValueError(f"Target model '{target_model}' not found in registry")

        mapper: Mapper = sa.inspect(model_cls)
        direct_cols = {col.name: col for col in mapper.columns}

        stmt = sa.select().select_from(model_cls)
        joins_registry: Dict[str, Any] = {}
        where_clauses = []

        if hasattr(model_cls, "company_id"):
            where_clauses.append(getattr(model_cls, "company_id") == company_id)

        if hasattr(model_cls, "deleted_at"):
            where_clauses.append(getattr(model_cls, "deleted_at").is_(None))

        columns_meta: List[Dict[str, Any]] = []
        is_grouped = bool(group_by and aggregations)

        # 1. Grouped Aggregation vs Flat Tabular Selection
        if is_grouped:
            select_exprs = []
            group_exprs = []

            # Group By Columns (supports direct and dot-notation)
            for col_name in (group_by or []):
                col_expr, col_type, title, stmt = cls._resolve_column_expression(
                    model_cls, col_name, joins_registry, stmt
                )
                if col_expr is not None:
                    select_exprs.append(col_expr)
                    group_exprs.append(col_expr)
                    columns_meta.append({
                        "name": col_name,
                        "title": title,
                        "type": col_type,
                        "is_group": True,
                    })

            # Aggregate Columns (supports direct and dot-notation)
            for field_name, agg_func in (aggregations or {}).items():
                col_expr, col_type, title, stmt = cls._resolve_column_expression(
                    model_cls, field_name, joins_registry, stmt
                )
                if col_expr is not None:
                    agg_name = f"{field_name}_{agg_func}".replace(".", "_")
                    func_lower = agg_func.lower()

                    if func_lower == "count":
                        expr = sa.func.count(col_expr).label(agg_name)
                        out_type = "integer"
                    elif func_lower == "sum":
                        expr = sa.func.sum(col_expr).label(agg_name)
                        out_type = "float"
                    elif func_lower == "avg":
                        expr = sa.func.avg(col_expr).label(agg_name)
                        out_type = "float"
                    elif func_lower == "min":
                        expr = sa.func.min(col_expr).label(agg_name)
                        out_type = col_type
                    elif func_lower == "max":
                        expr = sa.func.max(col_expr).label(agg_name)
                        out_type = col_type
                    else:
                        continue

                    select_exprs.append(expr)
                    columns_meta.append({
                        "name": agg_name,
                        "title": f"{title} ({agg_func.upper()})",
                        "type": out_type,
                        "is_aggregate": True,
                    })

            stmt = stmt.add_columns(*select_exprs)
            for clause in where_clauses:
                stmt = stmt.where(clause)

            if group_exprs:
                stmt = stmt.group_by(*group_exprs)

        else:
            # Flat tabular query (supports direct and dot-notation paths)
            target_field_names = selected_fields or list(direct_cols.keys())
            select_cols = []

            for col_name in target_field_names:
                col_expr, col_type, title, stmt = cls._resolve_column_expression(
                    model_cls, col_name, joins_registry, stmt
                )
                if col_expr is not None:
                    select_cols.append(col_expr)
                    columns_meta.append({
                        "name": col_name,
                        "title": title,
                        "type": col_type,
                    })

            stmt = stmt.add_columns(*select_cols)
            for clause in where_clauses:
                stmt = stmt.where(clause)

        # 2. Order By (supports direct and dot-notation paths)
        if order_by:
            for ord_str in order_by:
                parts = ord_str.strip().split()
                col_name = parts[0]
                is_desc = len(parts) > 1 and parts[1].lower() == "desc"

                col_expr, _, _, stmt = cls._resolve_column_expression(
                    model_cls, col_name, joins_registry, stmt
                )
                if col_expr is not None:
                    stmt = stmt.order_by(col_expr.desc() if is_desc else col_expr.asc())
        elif hasattr(model_cls, "created_at") and not is_grouped:
            stmt = stmt.order_by(getattr(model_cls, "created_at").desc())

        stmt = stmt.limit(limit)

        # 3. Execute Query
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

        # 4. Apply AST Condition filtering if provided on flat queries
        if filters and not is_grouped:
            rows = [r for r in rows if ASTConditionEvaluator.evaluate(filters, r)]

        # 5. Calculate Grand Totals across numeric columns
        for col_meta in columns_meta:
            c_name = col_meta["name"]
            c_type = col_meta["type"]
            if c_type in ("integer", "float"):
                numeric_vals = [
                    r[c_name]
                    for r in rows
                    if r.get(c_name) is not None and isinstance(r.get(c_name), (int, float))
                ]
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

    @classmethod
    async def execute_document_query(
        cls,
        db: AsyncSession,
        company_id: uuid.UUID,
        target_model: str,
        record_id: uuid.UUID,
        header_fields: Optional[List[str]] = None,
        recipient_fields: Optional[List[str]] = None,
        lines_relationship: Optional[str] = None,
        lines_fields: Optional[List[str]] = None,
        document_title: Optional[str] = None,
    ) -> ReportDataResult:
        """
        Execute transactional document query for a single entity (Invoice, Sales Order, etc.),
        loading the parent record with dot-notation header/recipient fields, and iterating 1:M child lines.
        """
        model_cls = find_model_class(target_model)
        if not model_cls:
            raise ValueError(f"Target model '{target_model}' not found in registry")

        root_mapper: Mapper = sa.inspect(model_cls)

        # 1. Resolve Parent Document (Header & Recipient Cards)
        parent_stmt = sa.select().select_from(model_cls)
        parent_joins: Dict[str, Any] = {}
        parent_where = [getattr(model_cls, "id") == record_id]

        if hasattr(model_cls, "company_id"):
            parent_where.append(getattr(model_cls, "company_id") == company_id)
        if hasattr(model_cls, "deleted_at"):
            parent_where.append(getattr(model_cls, "deleted_at").is_(None))

        header_target = header_fields or ["id", "created_at"]
        recipient_target = recipient_fields or []
        combined_parent_fields = list(dict.fromkeys(header_target + recipient_target))

        parent_select_exprs = []
        parent_columns_meta: List[Dict[str, Any]] = []

        for field in combined_parent_fields:
            expr, c_type, title, parent_stmt = cls._resolve_column_expression(
                model_cls, field, parent_joins, parent_stmt
            )
            if expr is not None:
                parent_select_exprs.append(expr)
                parent_columns_meta.append({"name": field, "title": title, "type": c_type})

        # If no explicit fields found, select all direct columns
        if not parent_select_exprs:
            for c in root_mapper.columns:
                parent_select_exprs.append(getattr(model_cls, c.name).label(c.name))
                parent_columns_meta.append({"name": c.name, "title": _humanize_name(c.name), "type": _resolve_type_name(c.type)})

        parent_stmt = parent_stmt.add_columns(*parent_select_exprs)
        for clause in parent_where:
            parent_stmt = parent_stmt.where(clause)

        parent_res = await db.execute(parent_stmt)
        raw_parent = parent_res.first()
        if not raw_parent:
            raise ValueError(f"{target_model} record '{record_id}' not found or belongs to another company")

        parent_row_dict: Dict[str, Any] = {}
        if hasattr(raw_parent, "_mapping"):
            for meta in parent_columns_meta:
                k = meta["name"]
                v = raw_parent._mapping.get(k)
                if isinstance(v, (datetime.datetime, datetime.date)):
                    v = v.isoformat()
                elif isinstance(v, uuid.UUID):
                    v = str(v)
                parent_row_dict[k] = v

        header_data = {k: parent_row_dict.get(k) for k in header_target if k in parent_row_dict}
        recipient_data = {k: parent_row_dict.get(k) for k in recipient_target if k in parent_row_dict}

        # 2. Resolve 1:M Child Line Items
        lines_rows: List[Dict[str, Any]] = []
        lines_meta: List[Dict[str, Any]] = []
        lines_totals: Dict[str, Any] = {}

        if lines_relationship and lines_relationship in root_mapper.relationships:
            rel = root_mapper.relationships[lines_relationship]
            line_model = getattr(rel.entity, "class_", None) or getattr(rel.mapper, "class_", None)

            if line_model:
                line_mapper: Mapper = sa.inspect(line_model)
                line_stmt = sa.select().select_from(line_model)
                line_joins: Dict[str, Any] = {}

                # Find foreign key connecting line to parent
                fk_col_name = None
                for col in line_mapper.columns:
                    for fk in col.foreign_keys:
                        if fk.column.table.name == root_mapper.persist_selectable.name:
                            fk_col_name = col.name
                            break
                    if fk_col_name:
                        break

                line_where = []
                if fk_col_name:
                    line_where.append(getattr(line_model, fk_col_name) == record_id)
                elif hasattr(line_model, f"{target_model.lower()}_id"):
                    line_where.append(getattr(line_model, f"{target_model.lower()}_id") == record_id)

                if hasattr(line_model, "company_id"):
                    line_where.append(getattr(line_model, "company_id") == company_id)
                if hasattr(line_model, "deleted_at"):
                    line_where.append(getattr(line_model, "deleted_at").is_(None))

                target_line_fields = lines_fields or [
                    c.name
                    for c in line_mapper.columns
                    if c.name not in ("id", "company_id", "deleted_at", "created_at", "updated_at", fk_col_name)
                ]

                line_selects = []
                for lf in target_line_fields:
                    l_expr, l_type, l_title, line_stmt = cls._resolve_column_expression(
                        line_model, lf, line_joins, line_stmt
                    )
                    if l_expr is not None:
                        line_selects.append(l_expr)
                        lines_meta.append({"name": lf, "title": l_title, "type": l_type})

                line_stmt = line_stmt.add_columns(*line_selects)
                for lw in line_where:
                    line_stmt = line_stmt.where(lw)

                if hasattr(line_model, "created_at"):
                    line_stmt = line_stmt.order_by(getattr(line_model, "created_at").asc())

                line_res = await db.execute(line_stmt)
                raw_lines = line_res.all()

                for rl in raw_lines:
                    row_d: Dict[str, Any] = {}
                    if hasattr(rl, "_mapping"):
                        for lm in lines_meta:
                            k = lm["name"]
                            v = rl._mapping.get(k)
                            if isinstance(v, (datetime.datetime, datetime.date)):
                                v = v.isoformat()
                            elif isinstance(v, uuid.UUID):
                                v = str(v)
                            row_d[k] = v
                    lines_rows.append(row_d)

                # Compute totals for numeric columns on lines
                for lm in lines_meta:
                    if lm["type"] in ("integer", "float"):
                        c_name = lm["name"]
                        num_vals = [
                            r[c_name]
                            for r in lines_rows
                            if r.get(c_name) is not None and isinstance(r.get(c_name), (int, float))
                        ]
                        if num_vals:
                            lines_totals[c_name] = round(sum(num_vals), 4)

        doc_title = document_title or f"{_humanize_name(target_model)} Document"

        return ReportDataResult(
            report_code=f"document.{target_model.lower()}",
            report_name=doc_title,
            target_model=target_model,
            columns=lines_meta if lines_rows else parent_columns_meta,
            rows=lines_rows if lines_rows else [parent_row_dict],
            aggregates=lines_totals,
            total_rows=len(lines_rows) if lines_rows else 1,
            generated_at=datetime.datetime.utcnow().isoformat(),
            metadata={
                "report_type": "document",
                "document_title": doc_title,
                "record_id": str(record_id),
                "header": header_data,
                "recipient": recipient_data,
                "has_lines": bool(lines_rows),
                "lines_count": len(lines_rows),
            },
        )
