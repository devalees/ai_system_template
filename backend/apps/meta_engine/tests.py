"""
Unit Tests for apps.meta_engine Metadata Catalog Models.
"""

import uuid
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import RequestFactory, TestCase, TransactionTestCase

from apps.core.middleware import CurrentUserMiddleware
from apps.meta_engine.models import (
    MetaAction,
    MetaField,
    MetaMenu,
    MetaModel,
    MetaReport,
    MetaRule,
    MetaView,
)

User = get_user_model()


class MetaCatalogModelTests(TestCase):
    """
    Test suite verifying the integrity of the System Metadata Catalog models.
    """

    def setUp(self):
        self.user = User.objects.create_user(username="metadata_admin", password="password123")
        self.factory = RequestFactory()

    def test_meta_model_creation_and_cleaning(self):
        """Verify MetaModel slugification, table_name derivation, and audit fields."""
        model = MetaModel(
            name="Customer Invoice",
            label="Customer Invoice",
            app_label="invoicing",
        )
        model.clean()
        model.save()

        self.assertEqual(model.name, "customer_invoice")
        self.assertEqual(model.table_name, "app_customer_invoice")
        self.assertEqual(model.label_plural, "Customer Invoices")
        self.assertIsInstance(model.id, uuid.UUID)
        self.assertIsNotNone(model.created_at)
        self.assertIsNotNone(model.updated_at)

    def test_system_model_protection(self):
        """Verify system-level models cannot be deleted."""
        sys_model = MetaModel.objects.create(
            name="core_user",
            label="Core User",
            is_system=True,
        )
        with self.assertRaises(ValidationError):
            sys_model.delete()

    def test_meta_field_validation_and_reserved_names(self):
        """Verify field creation and prevention of reserved column names."""
        model = MetaModel.objects.create(name="crm_lead", label="Lead", app_label="crm")

        # Standard field creation
        field_title = MetaField.objects.create(
            model=model,
            name="title",
            label="Lead Title",
            field_type="char",
            required=True,
        )
        self.assertEqual(field_title.model, model)
        self.assertTrue(field_title.required)

        # Reserved system name check
        field_reserved = MetaField(
            model=model,
            name="created_at",
            label="Created At",
            field_type="datetime",
            is_system=False,
        )
        with self.assertRaises(ValidationError):
            field_reserved.clean()

    def test_relational_meta_fields(self):
        """Verify foreign key dynamic reference linking between MetaModels."""
        partner_model = MetaModel.objects.create(name="res_partner", label="Partner", app_label="base")
        order_model = MetaModel.objects.create(name="sale_order", label="Sales Order", app_label="sale")

        fk_field = MetaField.objects.create(
            model=order_model,
            name="partner_id",
            label="Customer",
            field_type="foreign_key",
            fk_target_model=partner_model,
            on_delete_behavior="SET_NULL",
        )
        self.assertEqual(fk_field.fk_target_model, partner_model)
        self.assertIn(fk_field, partner_model.referencing_fields.all())

    def test_meta_view_and_actions(self):
        """Verify declarative views and attached window actions."""
        model = MetaModel.objects.create(name="helpdesk_ticket", label="Ticket", app_label="helpdesk")

        view = MetaView.objects.create(
            model=model,
            name="Ticket Kanban",
            view_type="kanban",
            is_default=True,
            layout_schema={"card": {"title": "subject", "badge": "priority"}},
        )
        self.assertTrue(view.is_default)
        self.assertEqual(view.view_type, "kanban")

        action = MetaAction.objects.create(
            name="Open Open Tickets",
            action_type="window",
            target_model=model,
            target_view=view,
            domain_filter={"status": "open"},
        )
        self.assertEqual(action.target_model, model)
        self.assertEqual(action.target_view, view)

    def test_meta_menu_hierarchy(self):
        """Verify parent-child navigation menus."""
        root_menu = MetaMenu.objects.create(name="CRM", app_label="crm", sequence=10)
        child_menu = MetaMenu.objects.create(name="Leads", parent=root_menu, app_label="crm", sequence=10)

        self.assertIn(child_menu, root_menu.children.all())
        self.assertEqual(str(child_menu), "CRM ➔ Leads [crm]")

    def test_meta_rule_access_control(self):
        """Verify security access rules with row-level domain filtering."""
        model = MetaModel.objects.create(name="private_note", label="Note", app_label="notes")

        rule = MetaRule.objects.create(
            model=model,
            name="Owner Only Read",
            perm_read=True,
            perm_write=True,
            perm_delete=False,
            domain_filter={"created_by": "{{user.id}}"},
        )
        self.assertEqual(rule.model, model)
        self.assertFalse(rule.perm_delete)

    def test_meta_report_declarative_definition(self):
        """Verify declarative printable report templates."""
        model = MetaModel.objects.create(name="tax_invoice", label="Invoice", app_label="invoicing")

        report = MetaReport.objects.create(
            model=model,
            name="Tax Invoice PDF",
            slug="tax_invoice_standard",
            report_type="pdf",
            paper_format="A4",
            orientation="portrait",
            template_dsl="<html><body><h1>Invoice {{record.number}}</h1></body></html>",
            is_default=True,
        )
        self.assertEqual(report.slug, "tax_invoice_standard")
        self.assertTrue(report.is_default)
        self.assertEqual(report.paper_format, "A4")

    def test_metadata_audit_tracking_via_middleware(self):
        """Verify all metadata catalog records automatically populate created_by and updated_by."""
        request = self.factory.get("/")
        request.user = self.user

        middleware = CurrentUserMiddleware(
            lambda req: MetaModel.objects.create(name="audited_entity", label="Audited Entity")
        )
        model = middleware(request)

        self.assertEqual(model.created_by, self.user)
        self.assertEqual(model.updated_by, self.user)


class DynamicSchemaEngineTests(TransactionTestCase):
    """
    Test suite verifying PostgreSQL DDL operations via DynamicSchemaEngine.
    """

    def test_dynamic_table_lifecycle(self):
        """Verify dynamic CREATE TABLE, ADD COLUMN, DROP COLUMN, and DROP TABLE operations."""
        from apps.meta_engine.schema_engine import DynamicSchemaEngine

        meta_model = MetaModel.objects.create(
            name="test_warehouse_item",
            label="Warehouse Item",
            app_label="inventory",
        )

        # 1. Verify physical table was created in PostgreSQL
        table_name = meta_model.table_name
        self.assertTrue(DynamicSchemaEngine.table_exists(table_name))

        # 2. Verify base kernel audit columns exist
        columns = DynamicSchemaEngine.get_existing_columns(table_name)
        self.assertIn("id", columns)
        self.assertIn("created_at", columns)
        self.assertIn("updated_at", columns)
        self.assertIn("created_by_id", columns)
        self.assertIn("updated_by_id", columns)

        # 3. Add dynamic columns
        field_sku = MetaField.objects.create(
            model=meta_model,
            name="sku",
            label="SKU Code",
            field_type="char",
            max_length=64,
            required=True,
        )
        field_quantity = MetaField.objects.create(
            model=meta_model,
            name="quantity",
            label="Stock Quantity",
            field_type="integer",
            default_value="10",
        )

        self.assertTrue(DynamicSchemaEngine.column_exists(table_name, "sku"))
        self.assertTrue(DynamicSchemaEngine.column_exists(table_name, "quantity"))

        # 4. Drop dynamic column
        field_quantity.delete()
        self.assertFalse(DynamicSchemaEngine.column_exists(table_name, "quantity"))

        # 5. Drop dynamic table
        meta_model.delete()
        self.assertFalse(DynamicSchemaEngine.table_exists(table_name))


class DynamicModelFactoryTests(TransactionTestCase):
    """
    Test suite verifying in-memory compilation of live Django models from MetaModel definitions.
    """

    def test_dynamic_model_compilation_and_orm(self):
        """Verify dynamic model compilation, standard ORM CRUD queries, and audit headers."""
        from apps.meta_engine.model_factory import DynamicModelFactory
        from apps.meta_engine.schema_engine import DynamicSchemaEngine

        meta_model = MetaModel.objects.create(
            name="store_product",
            label="Store Product",
            app_label="shop",
        )
        MetaField.objects.create(
            model=meta_model,
            name="title",
            label="Product Title",
            field_type="char",
            max_length=150,
            required=True,
        )
        MetaField.objects.create(
            model=meta_model,
            name="price",
            label="Price",
            field_type="decimal",
            max_digits=10,
            decimal_places=2,
            required=True,
        )
        MetaField.objects.create(
            model=meta_model,
            name="in_stock",
            label="In Stock",
            field_type="boolean",
            default_value="true",
        )

        # 1. Compile in-memory model
        ProductClass = DynamicModelFactory.get_or_create_model(meta_model, force_reload=True)
        self.assertIsNotNone(ProductClass)
        self.assertEqual(ProductClass._meta.db_table, meta_model.table_name)

        # 2. Standard ORM Create
        product = ProductClass.objects.create(title="Ergonomic Keyboard", price="89.50", in_stock=True)
        self.assertIsInstance(product.id, uuid.UUID)
        self.assertIsNotNone(product.created_at)
        self.assertIsNotNone(product.updated_at)
        self.assertEqual(product.title, "Ergonomic Keyboard")
        self.assertEqual(str(product), "Ergonomic Keyboard")

        # 3. Standard ORM Filter & Count
        self.assertEqual(ProductClass.objects.filter(in_stock=True).count(), 1)

        # 4. Standard ORM Update
        product.price = "79.99"
        product.save()
        reloaded = ProductClass.objects.get(id=product.id)
        self.assertEqual(str(reloaded.price), "79.99")

        # Clean up
        meta_model.delete()

    def test_dynamic_model_soft_delete(self):
        """Verify dynamic model compilation with soft-delete paranoid manager."""
        from apps.meta_engine.model_factory import DynamicModelFactory

        meta_model = MetaModel.objects.create(
            name="client_contract",
            label="Client Contract",
            app_label="contracts",
            is_soft_delete=True,
        )
        MetaField.objects.create(
            model=meta_model,
            name="contract_number",
            label="Contract #",
            field_type="char",
            max_length=50,
            required=True,
        )

        ContractClass = DynamicModelFactory.get_or_create_model(meta_model, force_reload=True)

        contract = ContractClass.objects.create(contract_number="CTR-2026-001")
        self.assertFalse(contract.is_deleted)
        self.assertIsNone(contract.deleted_at)

        # Perform soft delete
        contract.delete()
        self.assertTrue(contract.is_deleted)
        self.assertEqual(ContractClass.objects.count(), 0)
        self.assertEqual(ContractClass.all_objects.count(), 1)
        self.assertEqual(ContractClass.objects.dead().count(), 1)

        # Restore
        contract.restore()
        self.assertFalse(contract.is_deleted)
        self.assertEqual(ContractClass.objects.count(), 1)

        meta_model.delete()
