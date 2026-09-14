"""CSV format renderer for report data with UTF-8 BOM encoding."""

import io
import csv
from modules.base.reporting.registry import ReportDataResult


class CSVReportRenderer:
    """Renders report data as RFC 4180 CSV with UTF-8 BOM support."""

    @classmethod
    def render(cls, data: ReportDataResult) -> bytes:
        """Render report rows and totals into CSV bytes."""
        output = io.StringIO()
        writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)

        # 1. Header row
        headers = [col["title"] for col in data.columns]
        writer.writerow(headers)

        # 2. Data rows
        col_names = [col["name"] for col in data.columns]
        for row in data.rows:
            writer.writerow([row.get(name, "") for name in col_names])

        # 3. Aggregates / Totals row if present
        if data.aggregates:
            total_row = []
            for i, col in enumerate(data.columns):
                c_name = col["name"]
                if c_name in data.aggregates:
                    total_row.append(f"TOTAL: {data.aggregates[c_name]}")
                elif i == 0:
                    total_row.append("GRAND TOTAL")
                else:
                    total_row.append("")
            writer.writerow(total_row)

        csv_str = output.getvalue()
        # UTF-8 BOM for Microsoft Excel compatibility across multilingual platforms
        return ("\ufeff" + csv_str).encode("utf-8")
