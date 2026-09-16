"""Default high-fidelity UI view definitions and layout fixtures for core business models."""

import uuid
import logging
from typing import Dict, Any, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.base.ui_schema.models import ViewDefinition
from modules.base.ui_schema.schemas import (
    FieldWidgetSchema,
    FormRowSchema,
    FormSectionSchema,
    FormTabSchema,
    StatusBarSchema,
    HeaderActionSchema,
    SidebarConfigSchema,
    FormViewSchema,
    ListColumnSchema,
    QuickFilterSchema,
    ListViewSchema,
    KanbanLaneSchema,
    KanbanCardBadgeSchema,
    KanbanCardSchema,
    KanbanViewSchema,
)

logger = logging.getLogger("sovereign.ui_schema.fixtures")

# ============================================================================
# Default System View Specifications
# ============================================================================

DEFAULT_SYSTEM_VIEWS: List[Dict[str, Any]] = [
    # ------------------------------------------------------------------------
    # 1. SaleOrder (Sales Orders & Quotations)
    # ------------------------------------------------------------------------
    {
        "res_model": "SaleOrder",
        "view_type": "form",
        "name": "Standard Sales Order Form",
        "layout_template": "split_chatter_right",
        "default_split_ratio": 65.0,
        "priority": 10,
        "is_default": True,
        "is_system": True,
        "schema": FormViewSchema(
            title_field="name",
            subtitle_field="state",
            status_bar=StatusBarSchema(
                field_name="state",
                stages=[
                    {"value": "draft", "label": "Quotation"},
                    {"value": "sent", "label": "Quotation Sent"},
                    {"value": "sale", "label": "Sales Order"},
                    {"value": "done", "label": "Locked"},
                    {"value": "cancelled", "label": "Cancelled"},
                ],
                clickable=False,
            ),
            header_actions=[
                HeaderActionSchema(id="confirm_order", label="Confirm Order", action_type="api_call", endpoint="/api/v1/sales/orders/{id}/confirm", method="POST", variant="primary", visible_states=["draft", "sent"]),
                HeaderActionSchema(id="create_invoice", label="Create Customer Invoice", action_type="api_call", endpoint="/api/v1/sales/orders/{id}/create-invoice", method="POST", variant="secondary", visible_states=["sale"]),
                HeaderActionSchema(id="cancel_order", label="Cancel", action_type="api_call", endpoint="/api/v1/sales/orders/{id}/cancel", method="POST", variant="destructive", visible_states=["draft", "sent"]),
            ],
            tabs=[
                FormTabSchema(
                    id="lines_tab",
                    label="Order Lines",
                    subgrid_relationship="lines",
                    subgrid_columns=[
                        FieldWidgetSchema(field_name="product_id", label="Product", widget_type="many2one_select", target_model="Product"),
                        FieldWidgetSchema(field_name="name", label="Description", widget_type="text", required=True),
                        FieldWidgetSchema(field_name="quantity", label="Quantity", widget_type="number", required=True),
                        FieldWidgetSchema(field_name="uom_id", label="Unit of Measure", widget_type="many2one_select", target_model="UOM"),
                        FieldWidgetSchema(field_name="unit_price", label="Unit Price", widget_type="currency", required=True),
                        FieldWidgetSchema(field_name="discount", label="Disc. %", widget_type="number"),
                        FieldWidgetSchema(field_name="price_subtotal", label="Subtotal", widget_type="currency", readonly=True),
                        FieldWidgetSchema(field_name="analytic_distribution", label="Analytic Distribution", widget_type="json_editor"),
                    ],
                ),
                FormTabSchema(
                    id="customer_info",
                    label="Customer & Invoicing",
                    sections=[
                        FormSectionSchema(
                            title="Partner Details",
                            rows=[
                                FormRowSchema(fields=[
                                    FieldWidgetSchema(field_name="partner_id", label="Customer", widget_type="many2one_select", target_model="Party", required=True),
                                    FieldWidgetSchema(field_name="date_order", label="Order Date", widget_type="datetime", required=True),
                                ]),
                                FormRowSchema(fields=[
                                    FieldWidgetSchema(field_name="analytic_account_id", label="Analytic Cost Center", widget_type="many2one_select", target_model="AnalyticAccount"),
                                    FieldWidgetSchema(field_name="currency_id", label="Currency", widget_type="many2one_select", target_model="Currency"),
                                ]),
                            ],
                        ),
                        FormSectionSchema(
                            title="Order Totals",
                            rows=[
                                FormRowSchema(fields=[
                                    FieldWidgetSchema(field_name="amount_untaxed", label="Untaxed Amount", widget_type="currency", readonly=True),
                                    FieldWidgetSchema(field_name="amount_tax", label="Taxes", widget_type="currency", readonly=True),
                                    FieldWidgetSchema(field_name="amount_total", label="Total Amount", widget_type="currency", readonly=True),
                                ]),
                            ],
                        ),
                    ],
                ),
            ],
            sidebar=SidebarConfigSchema(
                chatter_enabled=True,
                activities_enabled=True,
                audit_trail_enabled=True,
                dock_position="right",
                min_split_ratio=35.0,
                max_split_ratio=85.0,
                collapsible=True,
            ),
        ).model_dump(),
    },
    {
        "res_model": "SaleOrder",
        "view_type": "list",
        "name": "Standard Sales Orders List",
        "layout_template": "full_width",
        "default_split_ratio": 100.0,
        "priority": 10,
        "is_default": True,
        "is_system": True,
        "schema": ListViewSchema(
            columns=[
                ListColumnSchema(field_name="name", label="Number", widget_type="text", sortable=True, priority=1, default_visible=True),
                ListColumnSchema(field_name="date_order", label="Order Date", widget_type="datetime", sortable=True, priority=1, default_visible=True),
                ListColumnSchema(field_name="partner_id", label="Customer", widget_type="many2one_select", sortable=True, priority=1, default_visible=True),
                ListColumnSchema(field_name="state", label="Status", widget_type="badge", sortable=True, priority=1, default_visible=True),
                ListColumnSchema(field_name="amount_untaxed", label="Untaxed", widget_type="currency", sortable=True, align="right", priority=2, default_visible=True),
                ListColumnSchema(field_name="amount_total", label="Total", widget_type="currency", sortable=True, align="right", priority=1, default_visible=True),
            ],
            default_sort_field="date_order",
            default_sort_order="desc",
            search_fields=["name"],
            quick_filters=[
                QuickFilterSchema(id="quotations", label="Quotations", filter_expr={"state": "draft"}),
                QuickFilterSchema(id="confirmed_orders", label="Sales Orders", filter_expr={"state": "sale"}),
            ],
        ).model_dump(),
    },
    {
        "res_model": "SaleOrder",
        "view_type": "kanban",
        "name": "Sales Orders Pipeline",
        "layout_template": "full_width",
        "default_split_ratio": 100.0,
        "priority": 10,
        "is_default": True,
        "is_system": True,
        "schema": KanbanViewSchema(
            group_by_field="state",
            lanes=[
                KanbanLaneSchema(value="draft", label="Quotation", color="#64748b"),
                KanbanLaneSchema(value="sent", label="Quotation Sent", color="#3b82f6"),
                KanbanLaneSchema(value="sale", label="Sales Order", color="#10b981"),
                KanbanLaneSchema(value="done", label="Locked", color="#6b7280", is_folded=True),
                KanbanLaneSchema(value="cancelled", label="Cancelled", color="#ef4444", is_folded=True),
            ],
            card=KanbanCardSchema(
                title_field="name",
                subtitle_field="partner_id",
                badges=[KanbanCardBadgeSchema(field_name="state")],
                numeric_fields=["amount_total"],
            ),
            drag_drop_enabled=True,
        ).model_dump(),
    },

    # ------------------------------------------------------------------------
    # 2. PurchaseOrder (Purchases & Vendor Bills)
    # ------------------------------------------------------------------------
    {
        "res_model": "PurchaseOrder",
        "view_type": "form",
        "name": "Standard Purchase Order Form",
        "layout_template": "split_chatter_right",
        "default_split_ratio": 65.0,
        "priority": 10,
        "is_default": True,
        "is_system": True,
        "schema": FormViewSchema(
            title_field="name",
            subtitle_field="state",
            status_bar=StatusBarSchema(
                field_name="state",
                stages=[
                    {"value": "draft", "label": "RFQ"},
                    {"value": "sent", "label": "RFQ Sent"},
                    {"value": "to_approve", "label": "To Approve"},
                    {"value": "purchase", "label": "Purchase Order"},
                    {"value": "done", "label": "Locked"},
                    {"value": "cancelled", "label": "Cancelled"},
                ],
            ),
            header_actions=[
                HeaderActionSchema(id="confirm_po", label="Confirm Order", action_type="api_call", endpoint="/api/v1/purchases/orders/{id}/confirm", method="POST", variant="primary", visible_states=["draft", "sent"]),
                HeaderActionSchema(id="create_bill", label="Create Vendor Bill", action_type="api_call", endpoint="/api/v1/purchases/orders/{id}/create-bill", method="POST", variant="secondary", visible_states=["purchase"]),
            ],
            tabs=[
                FormTabSchema(
                    id="po_lines_tab",
                    label="Products & Services",
                    subgrid_relationship="lines",
                    subgrid_columns=[
                        FieldWidgetSchema(field_name="product_id", label="Product", widget_type="many2one_select", target_model="Product"),
                        FieldWidgetSchema(field_name="name", label="Description", widget_type="text", required=True),
                        FieldWidgetSchema(field_name="quantity", label="Quantity", widget_type="number", required=True),
                        FieldWidgetSchema(field_name="unit_price", label="Unit Price", widget_type="currency", required=True),
                        FieldWidgetSchema(field_name="price_subtotal", label="Subtotal", widget_type="currency", readonly=True),
                    ],
                ),
            ],
            sidebar=SidebarConfigSchema(
                chatter_enabled=True,
                activities_enabled=True,
                audit_trail_enabled=True,
                dock_position="right",
                min_split_ratio=35.0,
                max_split_ratio=85.0,
                collapsible=True,
            ),
        ).model_dump(),
    },
    {
        "res_model": "PurchaseOrder",
        "view_type": "list",
        "name": "Standard Purchase Orders List",
        "layout_template": "full_width",
        "default_split_ratio": 100.0,
        "priority": 10,
        "is_default": True,
        "is_system": True,
        "schema": ListViewSchema(
            columns=[
                ListColumnSchema(field_name="name", label="Reference", widget_type="text", sortable=True, priority=1, default_visible=True),
                ListColumnSchema(field_name="date_order", label="Order Date", widget_type="datetime", sortable=True, priority=1, default_visible=True),
                ListColumnSchema(field_name="partner_id", label="Vendor", widget_type="many2one_select", sortable=True, priority=1, default_visible=True),
                ListColumnSchema(field_name="state", label="Status", widget_type="badge", sortable=True, priority=1, default_visible=True),
                ListColumnSchema(field_name="amount_total", label="Total", widget_type="currency", sortable=True, align="right", priority=1, default_visible=True),
            ],
            default_sort_field="date_order",
            default_sort_order="desc",
            search_fields=["name"],
            quick_filters=[
                QuickFilterSchema(id="rfqs", label="RFQs", filter_expr={"state": "draft"}),
                QuickFilterSchema(id="orders", label="Purchase Orders", filter_expr={"state": "purchase"}),
            ],
        ).model_dump(),
    },

    # ------------------------------------------------------------------------
    # 3. AccountMove (Financial Invoices & Journal Entries)
    # ------------------------------------------------------------------------
    {
        "res_model": "AccountMove",
        "view_type": "form",
        "name": "Standard Financial Move Form",
        "layout_template": "split_chatter_right",
        "default_split_ratio": 65.0,
        "priority": 10,
        "is_default": True,
        "is_system": True,
        "schema": FormViewSchema(
            title_field="name",
            subtitle_field="move_type",
            status_bar=StatusBarSchema(
                field_name="state",
                stages=[
                    {"value": "draft", "label": "Draft"},
                    {"value": "posted", "label": "Posted"},
                    {"value": "cancelled", "label": "Cancelled"},
                ],
            ),
            header_actions=[
                HeaderActionSchema(id="post_move", label="Post Entry", action_type="api_call", endpoint="/api/v1/accounting/moves/{id}/post", method="POST", variant="primary", visible_states=["draft"]),
                HeaderActionSchema(id="cancel_move", label="Cancel Entry", action_type="api_call", endpoint="/api/v1/accounting/moves/{id}/cancel", method="POST", variant="destructive", visible_states=["draft", "posted"]),
            ],
            tabs=[
                FormTabSchema(
                    id="journal_items_tab",
                    label="Journal Items",
                    subgrid_relationship="lines",
                    subgrid_columns=[
                        FieldWidgetSchema(field_name="account_id", label="Account", widget_type="many2one_select", target_model="Account", required=True),
                        FieldWidgetSchema(field_name="partner_id", label="Partner", widget_type="many2one_select", target_model="Party"),
                        FieldWidgetSchema(field_name="name", label="Label", widget_type="text"),
                        FieldWidgetSchema(field_name="debit", label="Debit", widget_type="currency", required=True),
                        FieldWidgetSchema(field_name="credit", label="Credit", widget_type="currency", required=True),
                        FieldWidgetSchema(field_name="analytic_distribution", label="Analytic Distribution", widget_type="json_editor"),
                    ],
                ),
            ],
            sidebar=SidebarConfigSchema(
                chatter_enabled=True,
                activities_enabled=True,
                audit_trail_enabled=True,
                dock_position="right",
                min_split_ratio=35.0,
                max_split_ratio=85.0,
                collapsible=True,
            ),
        ).model_dump(),
    },
    {
        "res_model": "AccountMove",
        "view_type": "list",
        "name": "Standard Invoices & Journal Entries",
        "layout_template": "full_width",
        "default_split_ratio": 100.0,
        "priority": 10,
        "is_default": True,
        "is_system": True,
        "schema": ListViewSchema(
            columns=[
                ListColumnSchema(field_name="name", label="Number", widget_type="text", sortable=True, priority=1, default_visible=True),
                ListColumnSchema(field_name="date", label="Date", widget_type="date", sortable=True, priority=1, default_visible=True),
                ListColumnSchema(field_name="move_type", label="Type", widget_type="badge", sortable=True, priority=1, default_visible=True),
                ListColumnSchema(field_name="partner_id", label="Partner", widget_type="many2one_select", sortable=True, priority=1, default_visible=True),
                ListColumnSchema(field_name="amount_total", label="Total Amount", widget_type="currency", sortable=True, align="right", priority=1, default_visible=True),
                ListColumnSchema(field_name="state", label="Status", widget_type="badge", sortable=True, priority=1, default_visible=True),
            ],
            default_sort_field="date",
            default_sort_order="desc",
            search_fields=["name", "ref"],
            quick_filters=[
                QuickFilterSchema(id="cust_invoices", label="Customer Invoices", filter_expr={"move_type": "out_invoice"}),
                QuickFilterSchema(id="vendor_bills", label="Vendor Bills", filter_expr={"move_type": "in_invoice"}),
                QuickFilterSchema(id="posted_only", label="Posted", filter_expr={"state": "posted"}),
            ],
        ).model_dump(),
    },

    # ------------------------------------------------------------------------
    # 4. Product (Item Master Catalog)
    # ------------------------------------------------------------------------
    {
        "res_model": "Product",
        "view_type": "form",
        "name": "Standard Product Master Form",
        "layout_template": "split_chatter_right",
        "default_split_ratio": 65.0,
        "priority": 10,
        "is_default": True,
        "is_system": True,
        "schema": FormViewSchema(
            title_field="name",
            subtitle_field="code",
            tabs=[
                FormTabSchema(
                    id="general_info",
                    label="General Information",
                    sections=[
                        FormSectionSchema(
                            title="Product Identification",
                            rows=[
                                FormRowSchema(fields=[
                                    FieldWidgetSchema(field_name="name", label="Product Name", widget_type="text", required=True, col_span=2),
                                    FieldWidgetSchema(field_name="code", label="Internal Reference / SKU", widget_type="text", required=True),
                                ]),
                                FormRowSchema(fields=[
                                    FieldWidgetSchema(field_name="product_type", label="Product Type", widget_type="badge", required=True),
                                    FieldWidgetSchema(field_name="category_id", label="Category", widget_type="many2one_select", target_model="Category"),
                                    FieldWidgetSchema(field_name="uom_id", label="Default UoM", widget_type="many2one_select", target_model="UOM", required=True),
                                ]),
                            ],
                        ),
                        FormSectionSchema(
                            title="Pricing & Economics",
                            rows=[
                                FormRowSchema(fields=[
                                    FieldWidgetSchema(field_name="sale_price", label="Sales Price", widget_type="currency", required=True),
                                    FieldWidgetSchema(field_name="cost_price", label="Standard Cost", widget_type="currency", required=True),
                                    FieldWidgetSchema(field_name="is_active", label="Active", widget_type="boolean_switch"),
                                ]),
                            ],
                        ),
                    ],
                ),
                FormTabSchema(
                    id="accounting_defaults",
                    label="Accounting Defaults",
                    sections=[
                        FormSectionSchema(
                            title="GL Accounts & Default Taxes",
                            rows=[
                                FormRowSchema(fields=[
                                    FieldWidgetSchema(field_name="income_account_id", label="Income Account", widget_type="many2one_select", target_model="Account"),
                                    FieldWidgetSchema(field_name="expense_account_id", label="Expense Account", widget_type="many2one_select", target_model="Account"),
                                ]),
                            ],
                        ),
                    ],
                ),
            ],
            sidebar=SidebarConfigSchema(
                chatter_enabled=True,
                activities_enabled=True,
                audit_trail_enabled=True,
                dock_position="right",
                min_split_ratio=35.0,
                max_split_ratio=85.0,
                collapsible=True,
            ),
        ).model_dump(),
    },
    {
        "res_model": "Product",
        "view_type": "list",
        "name": "Standard Products Catalog List",
        "layout_template": "full_width",
        "default_split_ratio": 100.0,
        "priority": 10,
        "is_default": True,
        "is_system": True,
        "schema": ListViewSchema(
            columns=[
                ListColumnSchema(field_name="code", label="Internal Reference", widget_type="text", sortable=True, priority=1, default_visible=True),
                ListColumnSchema(field_name="name", label="Name", widget_type="text", sortable=True, priority=1, default_visible=True),
                ListColumnSchema(field_name="product_type", label="Type", widget_type="badge", sortable=True, priority=2, default_visible=True),
                ListColumnSchema(field_name="sale_price", label="Sales Price", widget_type="currency", sortable=True, align="right", priority=1, default_visible=True),
                ListColumnSchema(field_name="cost_price", label="Cost Price", widget_type="currency", sortable=True, align="right", priority=2, default_visible=True),
                ListColumnSchema(field_name="is_active", label="Active", widget_type="boolean", sortable=True, priority=3, default_visible=True),
            ],
            default_sort_field="name",
            default_sort_order="asc",
            search_fields=["code", "name"],
            quick_filters=[
                QuickFilterSchema(id="active_products", label="Active Products", filter_expr={"is_active": True}),
                QuickFilterSchema(id="storables", label="Storable Products", filter_expr={"product_type": "storable"}),
            ],
        ).model_dump(),
    },
    {
        "res_model": "Product",
        "view_type": "kanban",
        "name": "Product Visual Catalog Cards",
        "layout_template": "full_width",
        "default_split_ratio": 100.0,
        "priority": 10,
        "is_default": True,
        "is_system": True,
        "schema": KanbanViewSchema(
            group_by_field="product_type",
            lanes=[
                KanbanLaneSchema(value="storable", label="Storable Goods", color="#3b82f6"),
                KanbanLaneSchema(value="consumable", label="Consumables", color="#f59e0b"),
                KanbanLaneSchema(value="service", label="Services", color="#10b981"),
            ],
            card=KanbanCardSchema(
                title_field="name",
                subtitle_field="code",
                badges=[KanbanCardBadgeSchema(field_name="product_type")],
                numeric_fields=["sale_price"],
            ),
            drag_drop_enabled=True,
        ).model_dump(),
    },

    # ------------------------------------------------------------------------
    # 5. Party (Customers, Vendors & Contacts)
    # ------------------------------------------------------------------------
    {
        "res_model": "Party",
        "view_type": "form",
        "name": "Standard Party Profile Form",
        "layout_template": "split_chatter_right",
        "default_split_ratio": 65.0,
        "priority": 10,
        "is_default": True,
        "is_system": True,
        "schema": FormViewSchema(
            title_field="name",
            subtitle_field="email",
            tabs=[
                FormTabSchema(
                    id="contact_info",
                    label="Contact Information",
                    sections=[
                        FormSectionSchema(
                            title="General Info",
                            rows=[
                                FormRowSchema(fields=[
                                    FieldWidgetSchema(field_name="name", label="Full Name", widget_type="text", required=True),
                                    FieldWidgetSchema(field_name="email", label="Email", widget_type="text"),
                                ]),
                                FormRowSchema(fields=[
                                    FieldWidgetSchema(field_name="phone", label="Phone", widget_type="text"),
                                    FieldWidgetSchema(field_name="is_customer", label="Is Customer", widget_type="boolean_switch"),
                                    FieldWidgetSchema(field_name="is_supplier", label="Is Supplier", widget_type="boolean_switch"),
                                ]),
                            ],
                        ),
                    ],
                ),
            ],
            sidebar=SidebarConfigSchema(
                chatter_enabled=True,
                activities_enabled=True,
                audit_trail_enabled=True,
                dock_position="right",
                min_split_ratio=35.0,
                max_split_ratio=85.0,
                collapsible=True,
            ),
        ).model_dump(),
    },
    {
        "res_model": "Party",
        "view_type": "list",
        "name": "Standard Contacts & Parties List",
        "layout_template": "full_width",
        "default_split_ratio": 100.0,
        "priority": 10,
        "is_default": True,
        "is_system": True,
        "schema": ListViewSchema(
            columns=[
                ListColumnSchema(field_name="name", label="Name", widget_type="text", sortable=True, priority=1, default_visible=True),
                ListColumnSchema(field_name="email", label="Email", widget_type="text", sortable=True, priority=1, default_visible=True),
                ListColumnSchema(field_name="phone", label="Phone", widget_type="text", sortable=True, priority=2, default_visible=True),
                ListColumnSchema(field_name="is_customer", label="Customer", widget_type="boolean", sortable=True, priority=2, default_visible=True),
                ListColumnSchema(field_name="is_supplier", label="Supplier", widget_type="boolean", sortable=True, priority=2, default_visible=True),
            ],
            default_sort_field="name",
            default_sort_order="asc",
            search_fields=["name", "email", "phone"],
            quick_filters=[
                QuickFilterSchema(id="customers_only", label="Customers", filter_expr={"is_customer": True}),
                QuickFilterSchema(id="suppliers_only", label="Vendors", filter_expr={"is_supplier": True}),
            ],
        ).model_dump(),
    },

    # ------------------------------------------------------------------------
    # Multi-Template Screen Presets
    # ------------------------------------------------------------------------
    {
        "res_model": "SaleOrder",
        "view_type": "form",
        "template_code": "quick_entry",
        "name": "POS Quick Counter Entry",
        "description": "Streamlined full-width layout for high-throughput retail and counter sales",
        "layout_template": "full_width",
        "default_split_ratio": 100.0,
        "priority": 5,
        "is_default": False,
        "is_system": True,
        "schema": FormViewSchema(
            title_field="name",
            subtitle_field="partner_id",
            status_bar=StatusBarSchema(
                field_name="state",
                stages=[
                    {"value": "draft", "label": "Draft"},
                    {"value": "sale", "label": "Completed"},
                ],
                clickable=False,
            ),
            header_actions=[
                HeaderActionSchema(id="quick_pay", label="Quick Pay & Validate", action_type="api_call", endpoint="/api/v1/sales/orders/{id}/confirm", method="POST", variant="primary"),
            ],
            tabs=[
                FormTabSchema(
                    id="lines_tab",
                    label="Cart Items",
                    subgrid_relationship="lines",
                    subgrid_columns=[
                        FieldWidgetSchema(field_name="product_id", label="Item", widget_type="many2one_select", target_model="Product", required=True),
                        FieldWidgetSchema(field_name="quantity", label="Qty", widget_type="number", required=True),
                        FieldWidgetSchema(field_name="unit_price", label="Price", widget_type="currency", required=True),
                        FieldWidgetSchema(field_name="price_subtotal", label="Subtotal", widget_type="currency", readonly=True),
                    ],
                ),
                FormTabSchema(
                    id="quick_customer",
                    label="Customer & Register",
                    sections=[
                        FormSectionSchema(
                            title="Customer Info",
                            rows=[
                                FormRowSchema(fields=[
                                    FieldWidgetSchema(field_name="partner_id", label="Customer", widget_type="many2one_select", target_model="Party", required=True),
                                    FieldWidgetSchema(field_name="date_order", label="Date", widget_type="datetime", required=True),
                                ]),
                            ],
                        ),
                    ],
                ),
            ],
        ).model_dump(),
    },
    {
        "res_model": "SaleOrder",
        "view_type": "form",
        "template_code": "executive",
        "name": "Executive Sales Overview",
        "description": "High-level summary view focusing on financial margins, customer credit, and approval metrics",
        "layout_template": "split_chatter_right",
        "default_split_ratio": 60.0,
        "priority": 5,
        "is_default": False,
        "is_system": True,
        "schema": FormViewSchema(
            title_field="name",
            subtitle_field="state",
            status_bar=StatusBarSchema(
                field_name="state",
                stages=[
                    {"value": "draft", "label": "Quotation"},
                    {"value": "sale", "label": "Confirmed"},
                    {"value": "done", "label": "Locked"},
                ],
                clickable=False,
            ),
            header_actions=[
                HeaderActionSchema(id="exec_approve", label="Executive Approval", action_type="api_call", endpoint="/api/v1/sales/orders/{id}/confirm", method="POST", variant="primary"),
            ],
            tabs=[
                FormTabSchema(
                    id="exec_summary",
                    label="Financial Metrics",
                    sections=[
                        FormSectionSchema(
                            title="Key Performance Indicators",
                            rows=[
                                FormRowSchema(fields=[
                                    FieldWidgetSchema(field_name="partner_id", label="Client Account", widget_type="many2one_select", target_model="Party", readonly=True),
                                    FieldWidgetSchema(field_name="amount_total", label="Total Value", widget_type="currency", readonly=True),
                                ]),
                                FormRowSchema(fields=[
                                    FieldWidgetSchema(field_name="date_order", label="Booking Date", widget_type="datetime", readonly=True),
                                    FieldWidgetSchema(field_name="analytic_account_id", label="Cost Center", widget_type="many2one_select", target_model="AnalyticAccount", readonly=True),
                                ]),
                            ],
                        ),
                    ],
                ),
            ],
            sidebar=SidebarConfigSchema(
                chatter_enabled=True,
                activities_enabled=True,
                audit_trail_enabled=True,
                dock_position="right",
                min_split_ratio=40.0,
                max_split_ratio=80.0,
            ),
        ).model_dump(),
    },
    {
        "res_model": "AccountMove",
        "view_type": "form",
        "template_code": "simplified_invoice",
        "name": "Simplified Retail Tax Invoice",
        "description": "Streamlined invoice presentation for retail, cash receipts, and simplified tax documents",
        "layout_template": "full_width",
        "default_split_ratio": 100.0,
        "priority": 5,
        "is_default": False,
        "is_system": True,
        "schema": FormViewSchema(
            title_field="name",
            subtitle_field="move_type",
            status_bar=StatusBarSchema(
                field_name="state",
                stages=[
                    {"value": "draft", "label": "Draft Receipt"},
                    {"value": "posted", "label": "Posted Tax Invoice"},
                ],
                clickable=False,
            ),
            header_actions=[
                HeaderActionSchema(id="post_quick_invoice", label="Post Tax Invoice", action_type="api_call", endpoint="/api/v1/accounting/moves/{id}/post", method="POST", variant="primary"),
            ],
            tabs=[
                FormTabSchema(
                    id="invoice_items",
                    label="Items & Charges",
                    subgrid_relationship="lines",
                    subgrid_columns=[
                        FieldWidgetSchema(field_name="account_id", label="Revenue Account", widget_type="many2one_select", target_model="Account", required=True),
                        FieldWidgetSchema(field_name="name", label="Label", widget_type="text", required=True),
                        FieldWidgetSchema(field_name="credit", label="Amount", widget_type="currency", required=True),
                    ],
                ),
            ],
        ).model_dump(),
    },
    {
        "res_model": "Product",
        "view_type": "form",
        "template_code": "quick_product",
        "name": "Fast Item & SKU Creator",
        "description": "Compact card for rapid product, SKU, barcode, and pricing setup",
        "layout_template": "full_width",
        "default_split_ratio": 100.0,
        "priority": 5,
        "is_default": False,
        "is_system": True,
        "schema": FormViewSchema(
            title_field="name",
            subtitle_field="default_code",
            tabs=[
                FormTabSchema(
                    id="quick_info",
                    label="Essential Product Data",
                    sections=[
                        FormSectionSchema(
                            title="Identity & Pricing",
                            rows=[
                                FormRowSchema(fields=[
                                    FieldWidgetSchema(field_name="name", label="Item Name", widget_type="text", required=True),
                                    FieldWidgetSchema(field_name="default_code", label="Internal Reference / SKU", widget_type="text"),
                                ]),
                                FormRowSchema(fields=[
                                    FieldWidgetSchema(field_name="list_price", label="Sale Price", widget_type="currency", required=True),
                                    FieldWidgetSchema(field_name="standard_price", label="Cost Price", widget_type="currency"),
                                ]),
                            ],
                        ),
                    ],
                ),
            ],
        ).model_dump(),
    },
]


async def seed_system_default_views(db: AsyncSession) -> int:
    """Idempotently seed default system ViewDefinition records."""
    seeded_count = 0
    for data in DEFAULT_SYSTEM_VIEWS:
        tpl_code = data.get("template_code", "standard")
        stmt = select(ViewDefinition).where(
            ViewDefinition.res_model == data["res_model"],
            ViewDefinition.view_type == data["view_type"],
            ViewDefinition.template_code == tpl_code,
            ViewDefinition.is_system == True,
            ViewDefinition.deleted_at.is_(None),
        )
        existing = (await db.execute(stmt)).scalar_one_or_none()
        if not existing:
            view = ViewDefinition(
                company_id=None,
                res_model=data["res_model"],
                view_type=data["view_type"],
                template_code=tpl_code,
                name=data["name"],
                description=data.get("description"),
                target_role_ids=data.get("target_role_ids"),
                layout_template=data.get("layout_template", "split_chatter_right"),
                default_split_ratio=data.get("default_split_ratio", 65.0),
                priority=data.get("priority", 10),
                is_default=data.get("is_default", True),
                is_system=True,
                schema=data["schema"],
            )
            db.add(view)
            seeded_count += 1

    if seeded_count > 0:
        await db.commit()
        logger.info(f"Seeded {seeded_count} system default view definitions into ui_views.")

    return seeded_count
