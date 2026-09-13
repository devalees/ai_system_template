"""Universal Advanced Filtering AST Compiler, Aggregator & Pagination Engine."""

import re
import decimal
from typing import List, Dict, Any, Optional, Union, Literal
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import (
    select,
    func,
    and_,
    or_,
    not_,
    ColumnElement,
    Select,
    text,
    desc,
    asc,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase

OperatorType = Literal[
    "eq",
    "neq",
    "gt",
    "gte",
    "lt",
    "lte",
    "contains",
    "icontains",
    "starts_with",
    "ends_with",
    "in",
    "not_in",
    "between",
    "is_null",
]

SortDirection = Literal["asc", "desc"]
AggregateFunc = Literal["SUM", "AVG", "MIN", "MAX", "COUNT", "COUNT_DISTINCT"]
DateTruncType = Literal["day", "week", "month", "quarter", "year"]


# ------------------------------------------------------------------------------
# 1. Filter AST Models
# ------------------------------------------------------------------------------

class FilterNode(BaseModel):
    """Leaf node in query AST representing an atomic comparison expression."""
    field: str = Field(..., description="Target model column or JSONB path (e.g. 'amount', 'custom_fields.tier')")
    operator: OperatorType = Field(..., description="Comparison operator")
    value: Any = Field(default=None, description="Operand value or list of values for between/in")


class FilterGroup(BaseModel):
    """Compound node in query AST combining sub-conditions with boolean logic (AND/OR)."""
    logical_operator: Literal["AND", "OR"] = Field(default="AND", description="Boolean combinator")
    conditions: List[Union[FilterNode, "FilterGroup"]] = Field(
        default_factory=list,
        description="List of nested FilterNode comparisons or sub FilterGroup blocks",
    )


# Enable recursive model references
FilterGroup.model_rebuild()


class SortParam(BaseModel):
    """Sorting criterion."""
    field: str
    direction: SortDirection = "asc"


class PaginationParams(BaseModel):
    """Standardized pagination parameters."""
    page: int = Field(default=1, ge=1, description="1-indexed page number")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page (max 100)")


class PaginatedResponse(BaseModel):
    """Enveloped response for paginated query listings."""
    items: List[Any]
    total_count: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_prev: bool


# ------------------------------------------------------------------------------
# 2. Aggregator Specification Models
# ------------------------------------------------------------------------------

class DimensionSpec(BaseModel):
    """Grouping dimension for aggregations with optional date truncation."""
    name: str = Field(..., description="Alias for dimension in output")
    field: str = Field(..., description="Target model field")
    date_trunc: Optional[DateTruncType] = Field(default=None, description="Date truncation interval")


class MetricSpec(BaseModel):
    """Calculated metric specification with conditional filter support."""
    name: str = Field(..., description="Alias for metric in output")
    field: Optional[str] = Field(default=None, description="Target field to aggregate (optional for COUNT)")
    function: AggregateFunc = Field(default="SUM", description="Aggregation function")
    filter: Optional[Union[FilterNode, FilterGroup]] = Field(
        default=None,
        description="Optional conditional filter applied to this aggregate (FILTER WHERE ...)",
    )


class AggregationQuery(BaseModel):
    """Universal Analytics & Aggregation Request Specification."""
    dimensions: List[DimensionSpec] = Field(default_factory=list)
    metrics: List[MetricSpec] = Field(..., min_length=1)
    filter: Optional[Union[FilterNode, FilterGroup]] = Field(default=None)
    equations: Dict[str, str] = Field(
        default_factory=dict,
        description="Arithmetic equations evaluated on aggregate metrics (e.g. {'margin': '(revenue - cost) / revenue * 100'})",
    )


# ------------------------------------------------------------------------------
# 3. Query Compiler & Execution Engine
# ------------------------------------------------------------------------------

class QueryEngine:
    """Compiles declarative AST query trees, pagination, and metrics into parameterized SQLAlchemy expressions."""

    @classmethod
    def compile_filter(
        cls,
        model: type[DeclarativeBase],
        ast: Union[FilterNode, FilterGroup, Dict[str, Any]],
    ) -> Optional[ColumnElement[bool]]:
        """Compile AST filter node or group into SQLAlchemy binary boolean clause."""
        if not ast:
            return None

        # Coerce dicts into Pydantic models if needed
        if isinstance(ast, dict):
            if "logical_operator" in ast or "conditions" in ast:
                ast = FilterGroup(**ast)
            else:
                ast = FilterNode(**ast)

        if isinstance(ast, FilterNode):
            return cls._compile_leaf_node(model, ast)
        elif isinstance(ast, FilterGroup):
            return cls._compile_group_node(model, ast)

        return None

    @classmethod
    def _resolve_column(cls, model: type[DeclarativeBase], field_name: str) -> Any:
        """Resolve model column or JSONB subfield expression."""
        if "." in field_name:
            parts = field_name.split(".", 1)
            parent_attr = getattr(model, parts[0], None)
            if parent_attr is not None and hasattr(parent_attr, "__getitem__"):
                # JSONB nested field access
                return parent_attr[parts[1]].as_string()
            raise ValueError(f"Field path '{field_name}' could not be resolved on model '{model.__name__}'.")

        col = getattr(model, field_name, None)
        if col is None:
            raise ValueError(f"Field '{field_name}' does not exist on model '{model.__name__}'.")
        return col

    @classmethod
    def _compile_leaf_node(cls, model: type[DeclarativeBase], node: FilterNode) -> ColumnElement[bool]:
        """Compile a single FilterNode into an SQL comparison operator."""
        col = cls._resolve_column(model, node.field)
        op = node.operator
        val = node.value

        if op == "eq":
            return col == val
        elif op == "neq":
            return col != val
        elif op == "gt":
            return col > val
        elif op == "gte":
            return col >= val
        elif op == "lt":
            return col < val
        elif op == "lte":
            return col <= val
        elif op == "contains":
            return col.contains(str(val))
        elif op == "icontains":
            return col.ilike(f"%{val}%")
        elif op == "starts_with":
            return col.startswith(str(val))
        elif op == "ends_with":
            return col.endswith(str(val))
        elif op == "in":
            if not isinstance(val, (list, tuple, set)):
                val = [val]
            return col.in_(val)
        elif op == "not_in":
            if not isinstance(val, (list, tuple, set)):
                val = [val]
            return col.not_in(val)
        elif op == "between":
            if not isinstance(val, (list, tuple)) or len(val) != 2:
                raise ValueError(f"Operator 'between' requires a 2-element list [min, max], got {val}")
            return col.between(val[0], val[1])
        elif op == "is_null":
            return col.is_(None) if bool(val) else col.is_not(None)
        else:
            raise ValueError(f"Unsupported filter operator: '{op}'")

    @classmethod
    def _compile_group_node(cls, model: type[DeclarativeBase], group: FilterGroup) -> Optional[ColumnElement[bool]]:
        """Compile a FilterGroup combining conditions with AND/OR."""
        clauses = []
        for cond in group.conditions:
            clause = cls.compile_filter(model, cond)
            if clause is not None:
                clauses.append(clause)

        if not clauses:
            return None

        if group.logical_operator.upper() == "OR":
            return or_(*clauses)
        return and_(*clauses)

    @classmethod
    def apply_pagination_and_sorting(
        cls,
        stmt: Select,
        model: type[DeclarativeBase],
        pagination: PaginationParams,
        sort: Optional[List[SortParam]] = None,
    ) -> Select:
        """Apply ORDER BY, LIMIT, and OFFSET to SQLAlchemy query."""
        if sort:
            for s in sort:
                col = cls._resolve_column(model, s.field)
                stmt = stmt.order_by(desc(col) if s.direction == "desc" else asc(col))

        offset = (pagination.page - 1) * pagination.page_size
        return stmt.offset(offset).limit(pagination.page_size)

    @classmethod
    async def execute_query(
        cls,
        session: AsyncSession,
        model: type[DeclarativeBase],
        filter_ast: Optional[Union[FilterNode, FilterGroup, Dict[str, Any]]] = None,
        sort: Optional[List[SortParam]] = None,
        pagination: Optional[PaginationParams] = None,
    ) -> PaginatedResponse:
        """Execute a full filtered, sorted, and paginated query, returning enveloped results."""
        pagination = pagination or PaginationParams(page=1, page_size=20)
        base_stmt = select(model)

        # 1. Apply filter clauses
        if filter_ast:
            clause = cls.compile_filter(model, filter_ast)
            if clause is not None:
                base_stmt = base_stmt.where(clause)

        # 2. Count total matching records
        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        total_count = (await session.execute(count_stmt)).scalar() or 0

        # 3. Apply sorting and pagination
        paged_stmt = cls.apply_pagination_and_sorting(base_stmt, model, pagination, sort)
        results = (await session.execute(paged_stmt)).scalars().all()

        total_pages = (total_count + pagination.page_size - 1) // pagination.page_size if total_count > 0 else 0

        return PaginatedResponse(
            items=[r.to_dict() if hasattr(r, "to_dict") else r for r in results],
            total_count=total_count,
            page=pagination.page,
            page_size=pagination.page_size,
            total_pages=total_pages,
            has_next=pagination.page < total_pages,
            has_prev=pagination.page > 1,
        )

    @classmethod
    async def execute_aggregation(
        cls,
        session: AsyncSession,
        model: type[DeclarativeBase],
        query: AggregationQuery,
    ) -> List[Dict[str, Any]]:
        """Compile and execute multi-dimensional aggregations, conditional filters, and equations."""
        select_cols = []
        group_by_cols = []
        col_aliases = []

        # 1. Compile Dimensions
        for dim in query.dimensions:
            col = cls._resolve_column(model, dim.field)
            if dim.date_trunc:
                expr = func.date_trunc(dim.date_trunc, col).label(dim.name)
            else:
                expr = col.label(dim.name)
            select_cols.append(expr)
            group_by_cols.append(expr)
            col_aliases.append(dim.name)

        # 2. Compile Metrics
        for metric in query.metrics:
            col = cls._resolve_column(model, metric.field) if metric.field else None
            fn_name = metric.function.upper()

            if fn_name == "COUNT":
                agg_expr = func.count(col if col is not None else text("*"))
            elif fn_name == "COUNT_DISTINCT":
                if col is None:
                    raise ValueError(f"COUNT_DISTINCT requires a field in metric '{metric.name}'.")
                agg_expr = func.count(func.distinct(col))
            elif fn_name == "SUM":
                agg_expr = func.sum(col)
            elif fn_name == "AVG":
                agg_expr = func.avg(col)
            elif fn_name == "MIN":
                agg_expr = func.min(col)
            elif fn_name == "MAX":
                agg_expr = func.max(col)
            else:
                raise ValueError(f"Unsupported aggregate function: '{metric.function}'")

            # Conditional aggregation (FILTER WHERE ...)
            if metric.filter:
                filter_clause = cls.compile_filter(model, metric.filter)
                if filter_clause is not None:
                    agg_expr = agg_expr.filter(filter_clause)

            select_cols.append(agg_expr.label(metric.name))
            col_aliases.append(metric.name)

        # 3. Construct Query
        stmt = select(*select_cols)

        # Global query filter
        if query.filter:
            global_clause = cls.compile_filter(model, query.filter)
            if global_clause is not None:
                stmt = stmt.where(global_clause)

        if group_by_cols:
            stmt = stmt.group_by(*group_by_cols)

        # 4. Execute Query
        rows = (await session.execute(stmt)).all()
        results = []

        for row in rows:
            row_dict = {}
            for i, alias in enumerate(col_aliases):
                val = row[i]
                # Convert timestamps, decimals, and numbers cleanly
                if hasattr(val, "isoformat"):
                    val = val.isoformat()
                elif isinstance(val, (int, float, decimal.Decimal)):
                    val = float(val)
                row_dict[alias] = val

            # 5. Evaluate Computed Equations
            for eq_name, equation_str in query.equations.items():
                row_dict[eq_name] = cls._evaluate_equation(equation_str, row_dict)

            results.append(row_dict)

        return results

    @classmethod
    def _evaluate_equation(cls, equation: str, context: Dict[str, Any]) -> Optional[float]:
        """Safely evaluate arithmetic equation across aggregated metric values."""
        # Replace variable names with their float values
        safe_eval_dict = {}
        for k, v in context.items():
            if isinstance(v, (int, float)):
                safe_eval_dict[k] = float(v)

        # Sanitize equation: allow only alphanumeric variable names and basic math symbols (+ - * / () .)
        if not re.match(r"^[a-zA-Z0-9_\s\+\-\*\/\(\)\.]+$", equation):
            return None

        try:
            # Evaluate expression in restricted namespace
            result = eval(equation, {"__builtins__": {}}, safe_eval_dict)
            return round(float(result), 4)
        except Exception:
            return None
