"""Executive PDF report renderer using ReportLab Platypus with company branding and running page counts."""

import io
from typing import Optional
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas

from modules.base.reporting.registry import ReportDataResult
from modules.base.reporting.models import ReportTemplate


class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas that computes and draws the total page count ('Page X of Y')."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_footer(num_pages)
            super().showPage()
        super().save()

    def draw_footer(self, total_pages: int):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))

        # Footer divider line
        self.setStrokeColor(colors.HexColor("#E2E8F0"))
        self.setLineWidth(0.5)
        self.line(36, 30, self._pagesize[0] - 36, 30)

        # Footer text
        footer_note = getattr(self, "footer_text", "") or "Sovereign Autonomous Platform • Confidential"
        self.drawString(36, 18, footer_note)

        # Page X of Y
        page_str = f"Page {self._pageNumber} of {total_pages}"
        self.drawRightString(self._pagesize[0] - 36, 18, page_str)
        self.restoreState()


class PDFReportRenderer:
    """Renders structured report results into professional executive PDF documents."""

    @classmethod
    def render(
        cls,
        data: ReportDataResult,
        template: Optional[ReportTemplate] = None,
    ) -> bytes:
        """Render report into PDF binary bytes."""
        buf = io.BytesIO()

        # Orientation & Page Size
        is_landscape = template and template.orientation == "landscape"
        page_size = landscape(letter) if is_landscape else letter
        printable_width = (page_size[0] - 72)  # 36pt margins on left & right

        # Color Theme
        primary_hex = template.primary_color if template and template.primary_color else "#1E3A8A"
        brand_color = colors.HexColor(primary_hex)

        doc = SimpleDocTemplate(
            buf,
            pagesize=page_size,
            leftMargin=36,
            rightMargin=36,
            topMargin=36,
            bottomMargin=45,
        )

        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            "ReportTitle",
            parent=styles["Heading1"],
            fontSize=16,
            leading=20,
            textColor=brand_color,
            fontName="Helvetica-Bold",
            spaceAfter=4,
        )
        company_style = ParagraphStyle(
            "CompanyTitle",
            parent=styles["Normal"],
            fontSize=11,
            leading=14,
            textColor=colors.HexColor("#0F172A"),
            fontName="Helvetica-Bold",
        )
        meta_style = ParagraphStyle(
            "MetaText",
            parent=styles["Normal"],
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#64748B"),
            fontName="Helvetica",
        )
        header_cell_style = ParagraphStyle(
            "HeaderCell",
            parent=styles["Normal"],
            fontSize=8,
            leading=10,
            textColor=colors.white,
            fontName="Helvetica-Bold",
            alignment=0,
        )
        data_cell_style = ParagraphStyle(
            "DataCell",
            parent=styles["Normal"],
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#1E293B"),
            fontName="Helvetica",
        )
        data_cell_right_style = ParagraphStyle(
            "DataCellRight",
            parent=data_cell_style,
            alignment=2,
        )
        total_cell_style = ParagraphStyle(
            "TotalCell",
            parent=styles["Normal"],
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#0F172A"),
            fontName="Helvetica-Bold",
            alignment=2,
        )

        story = []

        # 1. Company Branding & Metadata Block
        company_info = data.company_info or {}
        company_name = company_info.get("name", "Sovereign Platform")
        vat_id = company_info.get("vat_id") or company_info.get("tax_id")
        vat_str = f"Tax/VAT ID: {vat_id} • " if vat_id else ""
        currency_str = f"Currency: {company_info.get('currency', 'USD')} • "

        header_table_data = [
            [
                Paragraph(data.report_name, title_style),
                Paragraph(company_name, company_style),
            ],
            [
                Paragraph(f"Generated: {data.generated_at[:19]} UTC", meta_style),
                Paragraph(f"{vat_str}{currency_str}Status: Active", meta_style),
            ],
        ]
        header_table = Table(header_table_data, colWidths=[printable_width * 0.6, printable_width * 0.4])
        header_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ]))
        story.append(header_table)

        if template and template.header_text:
            story.append(Spacer(1, 4))
            story.append(Paragraph(template.header_text, meta_style))

        story.append(Spacer(1, 6))
        story.append(HRFlowable(width="100%", thickness=1, color=brand_color, spaceAfter=8))

        # 2. Tabular Data Rows
        num_cols = len(data.columns)
        if num_cols == 0:
            story.append(Paragraph("No columns defined for this report.", meta_style))
        else:
            col_w = printable_width / num_cols
            col_widths = [col_w] * num_cols

            table_rows = []

            # Header Row
            hdr_cells = []
            for col in data.columns:
                align_style = header_cell_style
                hdr_cells.append(Paragraph(col["title"], align_style))
            table_rows.append(hdr_cells)

            # Data Rows
            for row in data.rows:
                row_cells = []
                for col in data.columns:
                    val = row.get(col["name"])
                    val_str = str(val) if val is not None else "—"
                    is_num = col["type"] in ("integer", "float")
                    cell_style = data_cell_right_style if is_num else data_cell_style
                    row_cells.append(Paragraph(val_str, cell_style))
                table_rows.append(row_cells)

            # Totals Row
            if data.aggregates:
                tot_cells = []
                for i, col in enumerate(data.columns):
                    c_name = col["name"]
                    if c_name in data.aggregates:
                        tot_val = f"{data.aggregates[c_name]:,.2f}" if col["type"] == "float" else f"{data.aggregates[c_name]:,}"
                        tot_cells.append(Paragraph(tot_val, total_cell_style))
                    elif i == 0:
                        tot_cells.append(Paragraph("TOTAL", total_cell_style))
                    else:
                        tot_cells.append(Paragraph("", total_cell_style))
                table_rows.append(tot_cells)

            t = Table(table_rows, colWidths=col_widths, repeatRows=1)
            t_style = [
                ("BACKGROUND", (0, 0), (-1, 0), brand_color),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("LINEBELOW", (0, 0), (-1, 0), 1, brand_color),
                ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ]

            # Alternating row colors
            for r_idx in range(1, len(data.rows) + 1):
                if r_idx % 2 == 0:
                    t_style.append(("BACKGROUND", (0, r_idx), (-1, r_idx), colors.HexColor("#F8FAFC")))

            # Total row style
            if data.aggregates:
                last_row = len(table_rows) - 1
                t_style.append(("BACKGROUND", (0, last_row), (-1, last_row), colors.HexColor("#F1F5F9")))
                t_style.append(("LINEABOVE", (0, last_row), (-1, last_row), 1, brand_color))

            t.setStyle(TableStyle(t_style))
            story.append(t)

        # Build document with NumberedCanvas
        def make_canvas(*args, **kwargs):
            canv = NumberedCanvas(*args, **kwargs)
            canv.footer_text = template.footer_text if template and template.footer_text else None
            return canv

        doc.build(story, canvasmaker=make_canvas)
        return buf.getvalue()
