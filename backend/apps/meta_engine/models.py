"""
System Metadata Catalog Models for Dynamic Metadata-Driven Runtime.

Defines the declarative metadata models powering dynamic schemas,
declarative views, hierarchical menus, actions, security rules, and reports.
"""

from django.conf import settings
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.core.models import AuditableModel, UUIDModel


FIELD_TYPE_CHOICES = [
    ("char", _("Text (Single-line)")),
    ("text", _("Text (Multi-line)")),
    ("integer", _("Integer Number")),
    ("float", _("Floating-Point Number")),
    ("decimal", _("Precise Decimal / Currency")),
    ("boolean", _("Boolean Flag (Yes/No)")),
    ("date", _("Date")),
    ("datetime", _("Date & Timestamp")),
    ("json", _("JSON / Structured Data")),
    ("foreign_key", _("Relational Link (Foreign Key)")),
    ("many_to_many", _("Many-to-Many Relationship")),
    ("file", _("File / Media Attachment")),
]

ON_DELETE_CHOICES = [
    ("CASCADE", _("Cascade (Delete dependent records)")),
    ("SET_NULL", _("Set Null (Keep record, clear reference)")),
    ("PROTECT", _("Protect (Block deletion if referenced)")),
    ("RESTRICT", _("Restrict (Standard relational restriction)")),
]

VIEW_TYPE_CHOICES = [
    ("form", _("Form / Detail View")),
    ("list", _("List / Table View")),
    ("kanban", _("Kanban Card Board")),
    ("pivot", _("Pivot / Aggregation Table")),
    ("tree", _("Hierarchical Tree")),
]

ACTION_TYPE_CHOICES = [
    ("window", _("Open Window / Model View")),
    ("server", _("Run Server Action / Task")),
    ("report", _("Generate Printable Report")),
    ("url", _("Redirect to URL / Endpoint")),
]

REPORT_TYPE_CHOICES = [
    ("pdf", _("Vector PDF Document")),
    ("html", _("Interactive HTML Report")),
]

PAPER_FORMAT_CHOICES = [
    ("A4", _("Standard A4 (210 × 297 mm)")),
    ("Letter", _("US Letter (8.5 × 11 in)")),
    ("thermal_80mm", _("Thermal Receipt (80 mm)")),
]

ORIENTATION_CHOICES = [
    ("portrait", _("Portrait")),
    ("landscape", _("Landscape")),
]


MODULE_STATUS_CHOICES = [
    ("uninstalled", _("Not Installed")),
    ("installed", _("Installed")),
    ("to_upgrade", _("Upgrade Available")),
    ("error", _("Installation / Runtime Error")),
]


class SystemModule(UUIDModel, AuditableModel):
    """
    Registry for modular apps and declarative packages.
    Similar to Odoo's ir.module.module. Tracks app packages, metadata,
    status, dependencies, and installed components.
    """
    app_id = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        verbose_name=_("Module Identifier"),
        help_text=_("Unique identifier/slug for the app package (e.g. 'crm', 'contacts').")
    )
    name = models.CharField(
        max_length=150,
        verbose_name=_("Module Name"),
        help_text=_("Human-readable title (e.g. 'Customer Relationship Management').")
    )
    version = models.CharField(
        max_length=50,
        default="1.0.0",
        verbose_name=_("Version"),
    )
    category = models.CharField(
        max_length=100,
        default="General",
        verbose_name=_("Category"),
        help_text=_("Business category (e.g. 'Sales', 'Operations', 'Finance', 'Productivity').")
    )
    icon = models.CharField(
        max_length=100,
        default="box",
        verbose_name=_("Icon"),
        help_text=_("Icon identifier (e.g. 'users', 'briefcase', 'database').")
    )
    summary = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("Summary"),
        help_text=_("Short one-sentence summary.")
    )
    description = models.TextField(
        blank=True,
        verbose_name=_("Description"),
        help_text=_("Full description of the module capabilities.")
    )
    author = models.CharField(
        max_length=150,
        default="System",
        verbose_name=_("Author"),
    )
    website = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("Website / Repo"),
    )
    license = models.CharField(
        max_length=50,
        default="MIT",
        verbose_name=_("License"),
    )
    status = models.CharField(
        max_length=30,
        choices=MODULE_STATUS_CHOICES,
        default="uninstalled",
        db_index=True,
        verbose_name=_("Status"),
    )
    dependencies = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_("Dependencies"),
        help_text=_("List of app_ids required by this module.")
    )
    manifest_data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Manifest Data"),
        help_text=_("Full cached manifest payload.")
    )
    installed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Installed At"),
    )

    class Meta:
        ordering = ["category", "name"]
        verbose_name = _("System Module")
        verbose_name_plural = _("System Modules")

    def __str__(self):
        status_icon = "🟢" if self.status == "installed" else "⚪"
        return f"{status_icon} {self.name} ({self.app_id} v{self.version})"


class MetaModel(UUIDModel, AuditableModel):
    """
    Authoritative definition of a dynamic business entity.
    Represents an entity type (e.g. contacts, crm_lead, invoice) mapped
    to an underlying physical PostgreSQL table.
    """
    module = models.ForeignKey(
        SystemModule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="models",
        verbose_name=_("Parent Module"),
        help_text=_("Modular app package that introduced this metadata definition.")
    )
    name = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        verbose_name=_("Model Identifier"),
        help_text=_("Unique programmatic model slug (e.g. 'contacts_partner', 'crm_lead').")
    )
    label = models.CharField(
        max_length=150,
        verbose_name=_("Display Label"),
        help_text=_("Human-readable singular label (e.g. 'Contact', 'Lead').")
    )
    label_plural = models.CharField(
        max_length=150,
        blank=True,
        verbose_name=_("Plural Label"),
        help_text=_("Human-readable plural label (e.g. 'Contacts', 'Leads').")
    )
    app_label = models.CharField(
        max_length=100,
        db_index=True,
        default="general",
        verbose_name=_("Application Module"),
        help_text=_("Logical module or package grouping (e.g. 'crm', 'contacts', 'invoicing').")
    )
    table_name = models.CharField(
        max_length=120,
        unique=True,
        db_index=True,
        blank=True,
        verbose_name=_("Database Table Name"),
        help_text=_("Physical PostgreSQL table name (e.g. 'app_contacts_partner').")
    )
    description = models.TextField(
        blank=True,
        verbose_name=_("Description"),
        help_text=_("Purpose and business boundaries of this entity.")
    )
    is_system = models.BooleanField(
        default=False,
        verbose_name=_("Is System Protected"),
        help_text=_("System models are protected against deletion.")
    )
    is_auditable = models.BooleanField(
        default=True,
        verbose_name=_("Is Auditable"),
        help_text=_("If enabled, instances automatically track created_by, updated_by, created_at, updated_at.")
    )
    is_soft_delete = models.BooleanField(
        default=False,
        verbose_name=_("Supports Soft Delete"),
        help_text=_("If enabled, instances support paranoid soft deletion via SoftDeleteModel.")
    )
    is_tenant_aware = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name=_("Is Tenant Aware"),
        help_text=_("Enforces row-level multi-tenant isolation scoped to an Organization/Workspace.")
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Is Active"),
        help_text=_("Deactivated models are concealed from active navigation and API routes.")
    )
    ordering_field = models.CharField(
        max_length=100,
        default="-created_at",
        verbose_name=_("Default Order Field"),
        help_text=_("Default sorting field expression (e.g. '-created_at', 'sequence', 'name').")
    )

    class Meta:
        ordering = ["app_label", "name"]
        verbose_name = _("Metadata Model")
        verbose_name_plural = _("Metadata Models")

    def clean(self):
        super().clean()
        # Ensure clean lowercase slug for name
        if self.name:
            self.name = self.name.strip().lower().replace(" ", "_")
        # Ensure valid table_name prefix
        if not self.table_name:
            self.table_name = f"app_{self.name}"
        if not self.label_plural:
            self.label_plural = f"{self.label}s"

    def save(self, *args, **kwargs):
        if self.name:
            self.name = self.name.strip().lower().replace(" ", "_")
        if not self.table_name:
            self.table_name = f"app_{self.name}"
        if not self.label_plural:
            self.label_plural = f"{self.label}s"
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.is_system:
            raise ValidationError(f"System metadata model '{self.name}' is protected and cannot be deleted.")
        super().delete(*args, **kwargs)

    def __str__(self):
        status_icon = "🟢" if self.is_active else "⏸️"
        return f"{status_icon} {self.label} [{self.app_label}.{self.name}]"


class MetaField(UUIDModel, AuditableModel):
    """
    Attribute and column descriptor attached to a MetaModel.
    Maps directly to a database column in the physical PostgreSQL table.
    """
    model = models.ForeignKey(
        MetaModel,
        on_delete=models.CASCADE,
        related_name="fields",
        verbose_name=_("Target Model"),
        help_text=_("Parent metadata model that owns this field.")
    )
    name = models.CharField(
        max_length=100,
        verbose_name=_("Field Name"),
        help_text=_("Physical database column name (e.g. 'email', 'phone', 'company_id').")
    )
    label = models.CharField(
        max_length=150,
        verbose_name=_("Display Label"),
        help_text=_("User-facing label for forms and tables.")
    )
    field_type = models.CharField(
        max_length=30,
        choices=FIELD_TYPE_CHOICES,
        default="char",
        verbose_name=_("Data Type"),
        help_text=_("Relational or scalar data type.")
    )
    max_length = models.PositiveIntegerField(
        default=255,
        null=True,
        blank=True,
        verbose_name=_("Max Length"),
        help_text=_("Maximum character length for text fields.")
    )
    max_digits = models.PositiveSmallIntegerField(
        default=12,
        null=True,
        blank=True,
        verbose_name=_("Max Digits"),
        help_text=_("Maximum number of digits for precise decimal numbers.")
    )
    decimal_places = models.PositiveSmallIntegerField(
        default=2,
        null=True,
        blank=True,
        verbose_name=_("Decimal Places"),
        help_text=_("Number of decimal places for currency or percentages.")
    )
    required = models.BooleanField(
        default=False,
        verbose_name=_("Required"),
        help_text=_("If checked, null or blank values are rejected on save.")
    )
    unique = models.BooleanField(
        default=False,
        verbose_name=_("Unique"),
        help_text=_("Enforces a unique database constraint on this column.")
    )
    index = models.BooleanField(
        default=False,
        verbose_name=_("Indexed"),
        help_text=_("Creates a PostgreSQL B-Tree index on this column for fast searching.")
    )
    default_value = models.CharField(
        max_length=255,
        blank=True,
        default="",
        verbose_name=_("Default Value"),
        help_text=_("Raw default value assigned when no input is provided.")
    )
    choices = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_("Allowed Choices"),
        help_text=_("JSON list of allowed options: [{'value': 'draft', 'label': 'Draft'}].")
    )
    fk_target_model = models.ForeignKey(
        MetaModel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="referencing_fields",
        verbose_name=_("Foreign Key Dynamic Target"),
        help_text=_("Target dynamic MetaModel if field_type is foreign_key or many_to_many.")
    )
    fk_target_app_model = models.CharField(
        max_length=150,
        blank=True,
        default="",
        verbose_name=_("Foreign Key Static Target"),
        help_text=_("Target static Django model if pointing to kernel models (e.g. 'auth.User').")
    )
    on_delete_behavior = models.CharField(
        max_length=20,
        choices=ON_DELETE_CHOICES,
        default="SET_NULL",
        verbose_name=_("On Delete Behavior"),
        help_text=_("Relational cascade behavior on target deletion.")
    )
    help_text = models.TextField(
        blank=True,
        verbose_name=_("Field Help Text"),
        help_text=_("Explanatory tooltip displayed in UI forms.")
    )
    sequence = models.PositiveIntegerField(
        default=10,
        verbose_name=_("Sequence Order"),
        help_text=_("Display sequence for automatic form layout generation.")
    )
    is_system = models.BooleanField(
        default=False,
        verbose_name=_("Is System Protected"),
        help_text=_("System fields cannot be altered or removed.")
    )
    is_readonly = models.BooleanField(
        default=False,
        verbose_name=_("Read-Only"),
        help_text=_("Field value cannot be edited directly by users in UI forms.")
    )

    class Meta:
        ordering = ["sequence", "name"]
        unique_together = [("model", "name")]
        verbose_name = _("Metadata Field")
        verbose_name_plural = _("Metadata Fields")

    def clean(self):
        super().clean()
        if self.name:
            self.name = self.name.strip().lower().replace(" ", "_")
        # System field reserved names check
        reserved_names = {"id", "pk", "created_at", "updated_at", "created_by", "updated_by"}
        if self.name in reserved_names and not self.is_system:
            raise ValidationError(f"Field name '{self.name}' is reserved for the system kernel.")

    def save(self, *args, **kwargs):
        if self.name:
            self.name = self.name.strip().lower().replace(" ", "_")
        super().save(*args, **kwargs)

    def __str__(self):
        req_badge = "*" if self.required else ""
        return f"{self.label} ({self.name}{req_badge}) [{self.get_field_type_display()}]"


class MetaAction(UUIDModel, AuditableModel):
    """
    Action descriptor defining window opens, server tasks, reports, or redirects.
    """
    module = models.ForeignKey(
        SystemModule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="actions",
        verbose_name=_("Parent Module"),
    )
    name = models.CharField(
        max_length=150,
        verbose_name=_("Action Name"),
        help_text=_("Title of this action (e.g. 'Open All Leads', 'Generate Invoice PDF').")
    )
    action_type = models.CharField(
        max_length=20,
        choices=ACTION_TYPE_CHOICES,
        default="window",
        verbose_name=_("Action Type"),
        help_text=_("Classification of the operation executed.")
    )
    target_model = models.ForeignKey(
        MetaModel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="actions",
        verbose_name=_("Target Model"),
        help_text=_("Dynamic model contextual to this action.")
    )
    target_view = models.ForeignKey(
        "MetaView",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="triggered_actions",
        verbose_name=_("Target View"),
        help_text=_("Specific layout view opened by window action.")
    )
    domain_filter = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Domain Filter"),
        help_text=_("JSON query filter applied to the view (e.g. {'status': 'active'}).")
    )
    context = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Context"),
        help_text=_("Arbitrary context dictionary passed to the client or handler.")
    )
    server_handler = models.CharField(
        max_length=200,
        blank=True,
        default="",
        verbose_name=_("Server Handler Slug"),
        help_text=_("Registered action handler identifier (for action_type='server').")
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Is Active")
    )

    class Meta:
        ordering = ["name"]
        verbose_name = _("Metadata Action")
        verbose_name_plural = _("Metadata Actions")

    def __str__(self):
        return f"{self.name} [{self.get_action_type_display()}]"


class MetaView(UUIDModel, AuditableModel):
    """
    Declarative layout specification for forms, tables, Kanban, and pivot views.
    Stores the visual coordinate tree and widget properties as JSON.
    """
    module = models.ForeignKey(
        SystemModule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="views",
        verbose_name=_("Parent Module"),
    )
    model = models.ForeignKey(
        MetaModel,
        on_delete=models.CASCADE,
        related_name="views",
        verbose_name=_("Model"),
        help_text=_("Dynamic model displayed by this view.")
    )
    name = models.CharField(
        max_length=150,
        verbose_name=_("View Title"),
        help_text=_("Name of the view (e.g. 'Primary Form', 'Sales Pipeline Kanban').")
    )
    view_type = models.CharField(
        max_length=20,
        choices=VIEW_TYPE_CHOICES,
        default="form",
        verbose_name=_("View Type"),
        help_text=_("Visual presentation format.")
    )
    is_default = models.BooleanField(
        default=False,
        verbose_name=_("Is Default View"),
        help_text=_("Primary view opened when viewing this model.")
    )
    layout_schema = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Declarative Layout Schema"),
        help_text=_("Structured JSON layout specification (tabs, sections, columns, widgets).")
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Is Active")
    )

    class Meta:
        ordering = ["model__name", "view_type", "-is_default"]
        verbose_name = _("Metadata View")
        verbose_name_plural = _("Metadata Views")

    def __str__(self):
        default_tag = " [Default]" if self.is_default else ""
        return f"{self.name} ({self.get_view_type_display()}){default_tag}"


class MetaMenu(UUIDModel, AuditableModel):
    """
    Hierarchical navigation item linking UI menus to target actions and views.
    """
    module = models.ForeignKey(
        SystemModule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="menus",
        verbose_name=_("Parent Module"),
    )
    name = models.CharField(
        max_length=150,
        verbose_name=_("Menu Label"),
        help_text=_("Display label in navigation menus (e.g. 'CRM', 'Contacts', 'All Leads').")
    )
    icon = models.CharField(
        max_length=64,
        blank=True,
        default="folder",
        verbose_name=_("Icon Slug"),
        help_text=_("Icon identifier (e.g. 'users', 'briefcase', 'database').")
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
        verbose_name=_("Parent Menu"),
        help_text=_("Parent menu item for nested dropdowns or sub-menus.")
    )
    sequence = models.PositiveIntegerField(
        default=10,
        verbose_name=_("Sequence Order"),
        help_text=_("Display sequence order among sibling menus.")
    )
    app_label = models.CharField(
        max_length=100,
        db_index=True,
        default="general",
        verbose_name=_("Application Module"),
        help_text=_("Module identifier owning this navigation menu.")
    )
    action = models.ForeignKey(
        MetaAction,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="menus",
        verbose_name=_("Attached Action"),
        help_text=_("Action executed upon clicking this menu item.")
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Is Active")
    )

    class Meta:
        ordering = ["sequence", "name"]
        verbose_name = _("Metadata Menu")
        verbose_name_plural = _("Metadata Menus")

    def __str__(self):
        parent_prefix = f"{self.parent.name} ➔ " if self.parent else ""
        return f"{parent_prefix}{self.name} [{self.app_label}]"


class MetaRule(UUIDModel, AuditableModel):
    """
    Security and access control policy defining CRUD permissions and row-level domain filters.
    """
    module = models.ForeignKey(
        SystemModule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rules",
        verbose_name=_("Parent Module"),
    )
    model = models.ForeignKey(
        MetaModel,
        on_delete=models.CASCADE,
        related_name="security_rules",
        verbose_name=_("Target Model"),
        help_text=_("Dynamic model governed by this access policy.")
    )
    name = models.CharField(
        max_length=150,
        verbose_name=_("Rule Name"),
        help_text=_("Descriptive title of the security rule.")
    )
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="meta_rules",
        verbose_name=_("Target User Group"),
        help_text=_("Leave empty to apply to all authenticated users.")
    )
    perm_read = models.BooleanField(default=True, verbose_name=_("Allow Read"))
    perm_write = models.BooleanField(default=True, verbose_name=_("Allow Write"))
    perm_create = models.BooleanField(default=True, verbose_name=_("Allow Create"))
    perm_delete = models.BooleanField(default=False, verbose_name=_("Allow Delete"))
    domain_filter = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Row-Level Access Filter"),
        help_text=_("Contextual domain expression (e.g. {'created_by': '{{user.id}}'}).")
    )
    is_active = models.BooleanField(default=True, verbose_name=_("Is Active"))

    class Meta:
        ordering = ["model__name", "name"]
        verbose_name = _("Metadata Security Rule")
        verbose_name_plural = _("Metadata Security Rules")

    def __str__(self):
        grp = self.group.name if self.group else "Everyone"
        return f"{self.name} ({self.model.label} ➔ {grp})"


class MetaReport(UUIDModel, AuditableModel):
    """
    Declarative printable report definition (PDF / HTML) bound to a MetaModel.
    Supports CSS Paged Media pagination and model introspection placeholders.
    """
    module = models.ForeignKey(
        SystemModule,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reports",
        verbose_name=_("Parent Module"),
    )
    model = models.ForeignKey(
        MetaModel,
        on_delete=models.CASCADE,
        related_name="reports",
        verbose_name=_("Target Model"),
        help_text=_("Dynamic model generating data for this report.")
    )
    name = models.CharField(
        max_length=150,
        verbose_name=_("Report Name"),
        help_text=_("Display name (e.g. 'Tax Invoice PDF', 'Picking Slip').")
    )
    slug = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        verbose_name=_("Report Slug"),
        help_text=_("Programmatic identifier for print dispatch (e.g. 'invoice_standard').")
    )
    report_type = models.CharField(
        max_length=10,
        choices=REPORT_TYPE_CHOICES,
        default="pdf",
        verbose_name=_("Format"),
        help_text=_("Output document format.")
    )
    paper_format = models.CharField(
        max_length=20,
        choices=PAPER_FORMAT_CHOICES,
        default="A4",
        verbose_name=_("Paper Size"),
        help_text=_("Target paper standard.")
    )
    orientation = models.CharField(
        max_length=20,
        choices=ORIENTATION_CHOICES,
        default="portrait",
        verbose_name=_("Orientation"),
        help_text=_("Page printing orientation.")
    )
    template_dsl = models.TextField(
        default="",
        blank=True,
        verbose_name=_("Template Markup (HTML/CSS)"),
        help_text=_("HTML/CSS markup with CSS Paged Media rules and {{record.field}} placeholders.")
    )
    layout_schema = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Visual Coordinates"),
        help_text=_("Coordinate schema tree for drag-and-drop report builders.")
    )
    is_default = models.BooleanField(
        default=False,
        verbose_name=_("Is Default Report"),
        help_text=_("Primary report format triggered by default print button.")
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("Is Active")
    )

    class Meta:
        ordering = ["model__name", "name"]
        verbose_name = _("Metadata Report")
        verbose_name_plural = _("Metadata Reports")

    def __str__(self):
        return f"🖨️ {self.name} [{self.model.label}] ({self.report_type.upper()})"
