"""Universal Headless Reporting & Document Engine Module."""

from modules.base.reporting.models import ReportTemplate, ReportDefinition
from modules.base.reporting.registry import report_registry, BaseReport, ReportDataResult
from modules.base.reporting.fixtures import register_standard_reports
import modules.base.reporting.action_handler  # Registers GenerateReportActionHandler

# Automatically register standard reports on module import
register_standard_reports()
