"""JSON format serializer for report results."""

from typing import Dict, Any
from modules.base.reporting.registry import ReportDataResult


class JSONReportRenderer:
    """Renders report data as structured dictionary."""

    @classmethod
    def render(cls, data: ReportDataResult) -> Dict[str, Any]:
        """Convert ReportDataResult into JSON-serializable dictionary."""
        return data.model_dump()
