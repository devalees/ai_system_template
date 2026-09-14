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
from modules.base.automated_actions.introspection import _humanize_name


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

        # Check if rendering in Transactional Document Mode
        is_document_mode = bool(data.metadata and data.metadata.get("report_type") == "document")

        if is_document_mode:
            doc_meta = data.metadata or {}
            doc_title = doc_meta.get("document_title") or data.report_name
            header_dict = doc_meta.get("header") or {}
            recipient_dict = doc_meta.get("recipient") or {}

            # 1. Executive Document Header
            company_info = data.company_info or {}
            company_name = company_info.get("name", "Sovereign Enterprise")
            vat_id = company_info.get("vat_id") or company_info.get("tax_id")
            vat_str = f"Tax/VAT ID: {vat_id}<br/>" if vat_id else ""
            currency_str = f"Currency: {company_info.get('currency', 'USD')}"

            comp_details = f"<b>{company_name}</b><br/>{vat_str}{currency_str}"
            doc_details = f"<b>{doc_title.upper()}</b><br/>"
            doc_details += f"Ref: #{doc_meta.get('record_id', '')[:8]}<br/>"
            doc_details += f"Date: {data.generated_at[:10]}"

            top_table_data = [
                [Paragraph(comp_details, meta_style), Paragraph(doc_details, title_style)]
            ]
            top_table = Table(top_table_data, colWidths=[printable_width * 0.5, printable_width * 0.5])
            top_table.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ]))
            story.append(top_table)
            story.append(Spacer(1, 6))
            story.append(HRFlowable(width="100%", thickness=1.5, color=brand_color, spaceAfter=8))

            # 2. Recipient & Header Cards Box
            if recipient_dict or header_dict:
                recipient_lines = ["<b>BILLED TO / RECIPIENT:</b>"]
                for rk, rv in recipient_dict.items():
                    if rv:
                        recipient_lines.append(f"{_humanize_name(rk)}: {rv}")
                rec_text = "<br/>".join(recipient_lines) if recipient_lines else ""

                header_lines = ["<b>DOCUMENT DETAILS:</b>"]
                for hk, hv in header_dict.items():
                    if hv and hk not in ("id", "company_id"):
                        header_lines.append(f"{_humanize_name(hk)}: {hv}")
                hdr_text = "<br/>".join(header_lines) if header_lines else ""

                card_table_data = [
                    [
                        Paragraph(rec_text, meta_style),
                        Paragraph(hdr_text, meta_style),
                    ]
                ]
                card_table = Table(card_table_data, colWidths=[printable_width * 0.55, printable_width * 0.45])
                card_table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                    ("PADDING", (0, 0), (-1, -1), 6),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]))
                story.append(card_table)
                story.append(Spacer(1, 10))

            # 3. Line Items Table
            if data.columns:
                col_w = printable_width / len(data.columns)
                col_widths = [col_w] * len(data.columns)
                table_rows = []

                # Header Row
                table_rows.append([Paragraph(c["title"], header_cell_style) for c in data.columns])

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

                t = Table(table_rows, colWidths=col_widths, repeatRows=1)
                t_style = [
                    ("BACKGROUND", (0, 0), (-1, 0), brand_color),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("PADDING", (0, 0), (-1, -1), 4),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ]
                for r_idx in range(1, len(data.rows) + 1):
                    if r_idx % 2 == 0:
                        t_style.append(("BACKGROUND", (0, r_idx), (-1, r_idx), colors.HexColor("#F8FAFC")))
                t.setStyle(TableStyle(t_style))
                story.append(t)

            # 4. Financial Summary Block (Bottom Right)
            if data.aggregates:
                story.append(Spacer(1, 10))
                summary_rows = []
                for agg_key, agg_val in data.aggregates.items():
                    val_str = f"{agg_val:,.2f}" if isinstance(agg_val, float) else f"{agg_val:,}"
                    summary_rows.append([
                        Paragraph(f"<b>TOTAL {_humanize_name(agg_key).upper()}:</b>", total_cell_style),
                        Paragraph(val_str, total_cell_style),
                    ])

                summary_table = Table(summary_rows, colWidths=[printable_width * 0.7, printable_width * 0.3])
                summary_table.setStyle(TableStyle([
                    ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F1F5F9")),
                    ("BOX", (0, 0), (-1, -1), 0.5, brand_color),
                    ("PADDING", (0, 0), (-1, -1), 4),
                ]))
                story.append(summary_table)

        else:
            # Standard Tabular / Pivot Report Layout
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

            num_cols = len(data.columns)
            if num_cols == 0:
                story.append(Paragraph("No columns defined for this report.", meta_style))
            else:
                col_w = printable_width / num_cols
                col_widths = [col_w] * num_cols

                table_rows = []

                # Header Row
                table_rows.append([Paragraph(col["title"], header_cell_style) for col in data.columns])

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
                    ("PADDING", (0, 0), (-1, -1), 4),
                    ("LINEBELOW", (0, 0), (-1, 0), 1, brand_color),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                ]

                for r_idx in range(1, len(data.rows) + 1):
                    if r_idx % 2 == 0:
                        t_style.append(("BACKGROUND", (0, r_idx), (-1, r_idx), colors.HexColor("#F8FAFC")))

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
