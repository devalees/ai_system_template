"""Streaming parsers and byte generators for CSV, Excel (openpyxl), and JSON datasets."""

import io
import csv
import json
from typing import List, Dict, Any, Generator, Optional
import openpyxl


class DataProcessor:
    """Universal parser and generator for bulk data exchange formats."""

    @classmethod
    def parse_csv(cls, raw_bytes: bytes) -> List[Dict[str, Any]]:
        """Parse raw CSV bytes into list of dictionaries."""
        text_stream = io.StringIO(raw_bytes.decode("utf-8-sig", errors="replace"))
        reader = csv.DictReader(text_stream)
        return [dict(row) for row in reader]

    @classmethod
    def generate_csv(cls, rows: List[Dict[str, Any]], fieldnames: Optional[List[str]] = None) -> bytes:
        """Generate CSV formatted bytes from record dictionaries."""
        if not rows:
            return b""
        if not fieldnames:
            fieldnames = list(rows[0].keys())

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
        return output.getvalue().encode("utf-8")

    @classmethod
    def parse_excel(cls, raw_bytes: bytes) -> List[Dict[str, Any]]:
        """Parse Excel workbook (.xlsx) into list of dictionaries using first row as headers."""
        wb = openpyxl.load_workbook(filename=io.BytesIO(raw_bytes), data_only=True)
        sheet = wb.active
        rows = list(sheet.iter_rows(values_only=True))
        if not rows:
            return []

        headers = [str(h).strip() if h is not None else f"col_{idx}" for idx, h in enumerate(rows[0])]
        records = []
        for row in rows[1:]:
            if all(v is None for v in row):
                continue
            record = {}
            for idx, val in enumerate(row):
                if idx < len(headers):
                    record[headers[idx]] = str(val) if val is not None else None
            records.append(record)
        wb.close()
        return records

    @classmethod
    def generate_excel(cls, rows: List[Dict[str, Any]], fieldnames: Optional[List[str]] = None) -> bytes:
        """Generate Excel (.xlsx) workbook bytes from list of dictionaries."""
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Export"

        if rows:
            if not fieldnames:
                fieldnames = list(rows[0].keys())
            ws.append(fieldnames)
            for row in rows:
                ws.append([row.get(f) for f in fieldnames])
        else:
            if fieldnames:
                ws.append(fieldnames)

        output = io.BytesIO()
        wb.save(output)
        wb.close()
        return output.getvalue()

    @classmethod
    def parse_json(cls, raw_bytes: bytes) -> List[Dict[str, Any]]:
        """Parse JSON array bytes into list of dictionaries."""
        data = json.loads(raw_bytes.decode("utf-8"))
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            return [data]
        return []

    @classmethod
    def generate_json(cls, rows: List[Dict[str, Any]]) -> bytes:
        """Generate formatted JSON array bytes."""
        return json.dumps(rows, indent=2, default=str).encode("utf-8")

    @classmethod
    def parse_file(cls, file_format: str, content: bytes) -> List[Dict[str, Any]]:
        """Parse arbitrary supported format."""
        fmt = file_format.lower().lstrip(".")
        if fmt == "csv":
            return cls.parse_csv(content)
        elif fmt in ("xlsx", "xls", "excel"):
            return cls.parse_excel(content)
        elif fmt == "json":
            return cls.parse_json(content)
        else:
            raise ValueError(f"Unsupported import file format: '{file_format}'")

    @classmethod
    def generate_file(
        cls, file_format: str, rows: List[Dict[str, Any]], fieldnames: Optional[List[str]] = None
    ) -> bytes:
        """Generate bytes for requested export format."""
        fmt = file_format.lower().lstrip(".")
        if fmt == "csv":
            return cls.generate_csv(rows, fieldnames)
        elif fmt in ("xlsx", "xls", "excel"):
            return cls.generate_excel(rows, fieldnames)
        elif fmt == "json":
            return cls.generate_json(rows)
        else:
            raise ValueError(f"Unsupported export file format: '{file_format}'")
