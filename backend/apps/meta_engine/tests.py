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
    SystemModule,
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


class ModularAppRegistryTests(TransactionTestCase):
    """
    Test suite for Sub-task 5: Modular App Discovery, Topological Dependency
    Resolution, and Declarative Multi-Pass Package Installation.
    """

    def test_manifest_discovery_and_sync(self):
        """Verify AppManifestReader scans directory packages and creates SystemModule records."""
        from apps.meta_engine.manifest_reader import AppManifestReader
        from apps.meta_engine.models import SystemModule

        synced = AppManifestReader.sync_discovered_modules()
        app_ids = [m.app_id for m in synced]
        self.assertIn("contacts", app_ids)
        self.assertIn("crm", app_ids)

        contacts_mod = SystemModule.objects.get(app_id="contacts")
        self.assertEqual(contacts_mod.status, "uninstalled")
        self.assertEqual(contacts_mod.category, "Operations")

        crm_mod = SystemModule.objects.get(app_id="crm")
        self.assertEqual(crm_mod.dependencies, ["contacts"])

    def test_dependency_resolution_order_and_errors(self):
        """Verify topological sort, cycle detection, and missing dependency errors."""
        from apps.meta_engine.dependency_resolver import (
            CyclicDependencyError,
            DependencyResolver,
            MissingDependencyError,
        )

        dep_map = {
            "app_a": [],
            "app_b": ["app_a"],
            "app_c": ["app_b"],
        }
        order = DependencyResolver.resolve_install_order(["app_c"], dependency_map=dep_map, installed_app_ids=set())
        self.assertEqual(order, ["app_a", "app_b", "app_c"])

        # Test missing dependency error
        with self.assertRaises(MissingDependencyError):
            DependencyResolver.resolve_install_order(["unknown_app"], dependency_map=dep_map)

        # Test circular dependency detection
        cyclic_map = {
            "node_1": ["node_2"],
            "node_2": ["node_1"],
        }
        with self.assertRaises(CyclicDependencyError):
            DependencyResolver.resolve_install_order(["node_1"], dependency_map=cyclic_map, installed_app_ids=set())

    def test_end_to_end_app_installation(self):
        """Verify 1-click installation of CRM which auto-installs Contacts and builds relational schema."""
        from apps.meta_engine.app_installer import AppInstaller
        from apps.meta_engine.model_factory import DynamicModelFactory
        from apps.meta_engine.models import SystemModule
        from apps.meta_engine.schema_engine import DynamicSchemaEngine

        installed = AppInstaller.install("crm")
        installed_ids = [m.app_id for m in installed]
        self.assertEqual(installed_ids, ["contacts", "crm"])

        # 1. Verify SystemModule statuses
        contacts_mod = SystemModule.objects.get(app_id="contacts")
        crm_mod = SystemModule.objects.get(app_id="crm")
        self.assertEqual(contacts_mod.status, "installed")
        self.assertEqual(crm_mod.status, "installed")
        self.assertIsNotNone(contacts_mod.installed_at)
        self.assertIsNotNone(crm_mod.installed_at)

        # 2. Verify physical tables exist in PostgreSQL
        contacts_meta = MetaModel.objects.get(name="contacts_partner")
        crm_meta = MetaModel.objects.get(name="crm_lead")
        self.assertTrue(DynamicSchemaEngine.table_exists(contacts_meta.table_name))
        self.assertTrue(DynamicSchemaEngine.table_exists(crm_meta.table_name))

        # 3. Verify views and reports
        self.assertTrue(MetaView.objects.filter(model=crm_meta, view_type="kanban").exists())
        self.assertTrue(MetaReport.objects.filter(slug="crm_pipeline_summary_pdf").exists())
        self.assertTrue(MetaMenu.objects.filter(name="CRM").exists())

        # 4. Verify in-memory models and relational ORM execution
        PartnerClass = DynamicModelFactory.get_by_slug("contacts_partner")
        LeadClass = DynamicModelFactory.get_by_slug("crm_lead")
        self.assertIsNotNone(PartnerClass)
        self.assertIsNotNone(LeadClass)

        partner = PartnerClass.objects.create(name="Acme Global Corporation", email="info@acme.com", is_company=True)
        lead = LeadClass.objects.create(
            title="Enterprise Cloud Deal",
            partner_id=partner,
            expected_revenue="120000.00",
            stage="qualified",
            probability=60,
        )
        self.assertEqual(lead.partner_id.name, "Acme Global Corporation")
        self.assertEqual(str(lead.expected_revenue), "120000.00")

        # Clean up created records and metadata for idempotency
        crm_meta.delete()
        contacts_meta.delete()
        SystemModule.objects.filter(app_id__in=["contacts", "crm"]).delete()


class SafeAppUninstallerTests(TransactionTestCase):
    """
    Test suite for Sub-task 6: Safe App Uninstall, Reverse Dependency Guard,
    and Data Retention Policies (Archive, Snapshot Backup, Cascade Drop).
    """

    def setUp(self):
        from apps.meta_engine.app_installer import AppInstaller
        AppInstaller.install("crm")

    def tearDown(self):
        # Clean up any leftover metadata or physical tables for test isolation
        from apps.meta_engine.schema_engine import DynamicSchemaEngine
        for name in ["crm_lead", "contacts_partner"]:
            meta = MetaModel.objects.filter(name=name).first()
            if meta:
                try:
                    DynamicSchemaEngine.drop_table(meta)
                except Exception:
                    pass
                meta.delete()
        SystemModule.objects.filter(app_id__in=["crm", "contacts"]).delete()

    def test_reverse_dependency_guard_blocks_uninstall(self):
        """Verify uninstaller blocks removing 'contacts' while active 'crm' depends on it."""
        from apps.meta_engine.app_uninstaller import AppUninstaller, AppUninstallBlockedError

        with self.assertRaises(AppUninstallBlockedError) as ctx:
            AppUninstaller.uninstall("contacts")

        self.assertIn("crm", str(ctx.exception))
        self.assertEqual(SystemModule.objects.get(app_id="contacts").status, "installed")

    def test_uninstall_policy_archive(self):
        """Verify archive policy deactivates models/views but preserves physical PostgreSQL tables."""
        from apps.meta_engine.app_uninstaller import AppUninstaller
        from apps.meta_engine.schema_engine import DynamicSchemaEngine

        crm_meta = MetaModel.objects.get(name="crm_lead")
        table_name = crm_meta.table_name

        result = AppUninstaller.uninstall("crm", data_policy="archive")
        self.assertEqual(result["policy"], "archive")
        self.assertIn("crm_lead", result["models_affected"])

        # SystemModule marked uninstalled
        crm_mod = SystemModule.objects.get(app_id="crm")
        self.assertEqual(crm_mod.status, "uninstalled")

        # MetaModel soft deactivated
        crm_meta.refresh_from_db()
        self.assertFalse(crm_meta.is_active)

        # Physical database table remains intact
        self.assertTrue(DynamicSchemaEngine.table_exists(table_name))

    def test_uninstall_policy_snapshot_backup_and_drop(self):
        """Verify snapshot backup export and physical table drop."""
        import json
        import os
        from apps.meta_engine.app_uninstaller import AppUninstaller
        from apps.meta_engine.model_factory import DynamicModelFactory
        from apps.meta_engine.schema_engine import DynamicSchemaEngine

        LeadClass = DynamicModelFactory.get_by_slug("crm_lead")
        LeadClass.objects.create(title="Backup Test Lead", expected_revenue="50000.00")

        crm_meta = MetaModel.objects.get(name="crm_lead")
        table_name = crm_meta.table_name

        result = AppUninstaller.uninstall("crm", data_policy="snapshot_backup_and_drop")
        self.assertEqual(result["policy"], "snapshot_backup_and_drop")
        self.assertIsNotNone(result["backup_file"])
        self.assertTrue(os.path.exists(result["backup_file"]))

        # Check backup content
        with open(result["backup_file"], "r", encoding="utf-8") as bf:
            backup_json = json.load(bf)
        self.assertIn("crm_lead", backup_json["models"])
        self.assertEqual(backup_json["models"]["crm_lead"]["count"], 1)

        # Physical database table is dropped
        self.assertFalse(DynamicSchemaEngine.table_exists(table_name))

        # Clean up backup file
        try:
            os.remove(result["backup_file"])
        except Exception:
            pass

    def test_uninstall_policy_cascade_drop(self):
        """Verify cascade drop deletes metadata and physical database table directly."""
        from apps.meta_engine.app_uninstaller import AppUninstaller
        from apps.meta_engine.schema_engine import DynamicSchemaEngine

        crm_meta = MetaModel.objects.get(name="crm_lead")
        table_name = crm_meta.table_name

        result = AppUninstaller.uninstall("crm", data_policy="cascade_drop")
        self.assertEqual(result["policy"], "cascade_drop")

        # MetaModel is deleted
        self.assertFalse(MetaModel.objects.filter(name="crm_lead").exists())

        # Physical table is dropped
        self.assertFalse(DynamicSchemaEngine.table_exists(table_name))

        # Now contacts can be safely uninstalled since crm is uninstalled
        contacts_meta = MetaModel.objects.get(name="contacts_partner")
        contacts_table = contacts_meta.table_name
        AppUninstaller.uninstall("contacts", data_policy="cascade_drop")
        self.assertFalse(DynamicSchemaEngine.table_exists(contacts_table))


