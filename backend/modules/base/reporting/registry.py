"""Central registry and base classes for code-declared domain reports."""

import uuid
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Type
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("sovereign.reporting.registry")


class ReportDataResult(BaseModel):
    """Normalized structured data returned by any standard or dynamic report."""
    report_code: str
    report_name: str
    target_model: Optional[str] = None
    columns: List[Dict[str, Any]]
    rows: List[Dict[str, Any]]
    aggregates: Dict[str, Any] = {}
    total_rows: int
    generated_at: str
    company_info: Optional[Dict[str, Any]] = None


class BaseReport(ABC):
    """Abstract base class for all code-declared domain reports."""

    report_code: str = ""
    name: str = ""
    description: str = ""
    target_model: Optional[str] = None
    params_schema: Optional[Type[BaseModel]] = None
    supported_formats: List[str] = ["json", "csv", "xlsx", "pdf"]

    @abstractmethod
    async def get_data(
        self,
        db: AsyncSession,
        company_id: uuid.UUID,
        params: Dict[str, Any],
    ) -> ReportDataResult:
        """Execute database aggregations and return structured report data."""
        pass


class ReportRegistry:
    """Registry maintaining active standard report definitions."""

    def __init__(self):
        self._reports: Dict[str, BaseReport] = {}

    def register(self, report_cls: Type[BaseReport]) -> None:
        """Register a report class instance."""
        inst = report_cls()
        if not inst.report_code:
            raise ValueError(f"Report class {report_cls.__name__} must define a non-empty 'report_code'")
        self._reports[inst.report_code] = inst
        logger.info(f"Registered standard report: '{inst.report_code}' ({inst.name})")

    def get(self, report_code: str) -> Optional[BaseReport]:
        """Retrieve standard report by its code."""
        return self._reports.get(report_code)

    def list_all(self) -> List[BaseReport]:
        """List all registered report instances."""
        return list(self._reports.values())

    def get_catalog(self) -> List[Dict[str, Any]]:
        """Retrieve self-describing metadata for all registered reports."""
        catalog = []
        for r in self._reports.values():
            params_json_schema = (
                r.params_schema.model_json_schema() if r.params_schema else None
            )
            catalog.append({
                "code": r.report_code,
                "name": r.name,
                "description": r.description,
                "target_model": r.target_model,
                "supported_formats": r.supported_formats,
                "params_schema": params_json_schema,
                "is_dynamic": False,
            })
        return catalog


report_registry = ReportRegistry()
