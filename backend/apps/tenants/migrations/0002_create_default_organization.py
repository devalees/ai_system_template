from django.db import migrations


def create_default_organization(apps, schema_editor):
    Organization = apps.get_model("tenants", "Organization")
    OrganizationMembership = apps.get_model("tenants", "OrganizationMembership")
    User = apps.get_model("auth", "User")

    if not Organization.objects.filter(slug="default").exists():
        default_org = Organization.objects.create(
            name="Default Workspace",
            slug="default",
            tier="enterprise",
            max_users=100,
            is_active=True,
            metadata={"system_default": True, "description": "Global default workspace"}
        )

        for user in User.objects.all():
            role = "owner" if user.is_superuser else "member"
            OrganizationMembership.objects.get_or_create(
                organization=default_org,
                user=user,
                defaults={"role": role, "is_active": True}
            )


def reverse_default_organization(apps, schema_editor):
    Organization = apps.get_model("tenants", "Organization")
    Organization.objects.filter(slug="default").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("tenants", "0001_initial"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.RunPython(create_default_organization, reverse_default_organization),
    ]
