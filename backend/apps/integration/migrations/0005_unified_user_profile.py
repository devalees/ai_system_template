# Generated manually for unified Profile refactoring with zero data loss

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def populate_profile_defaults(apps, schema_editor):
    """Backfills is_agent and user_type for existing records."""
    Profile = apps.get_model('integration', 'Profile')
    for p in Profile.objects.all():
        # If linked to a bot user or has a canonical role, mark as agent
        is_bot = (p.user and p.user.username.startswith('bot_')) or bool(p.name)
        p.is_agent = is_bot
        p.user_type = 'agent' if is_bot else 'human'
        p.hermes_profile_name = p.name or ''
        p.save()


class Migration(migrations.Migration):

    dependencies = [
        ('integration', '0004_agentprofile_user_agenttask_created_by_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # 1. Rename existing AgentProfile to Profile (preserves existing table & data)
        migrations.RenameModel(
            old_name='AgentProfile',
            new_name='Profile',
        ),
        migrations.AlterModelOptions(
            name='profile',
            options={'ordering': ['user__username', 'created_at'], 'verbose_name': 'User Profile', 'verbose_name_plural': 'User Profiles'},
        ),
        # 2. Add new unified categorization fields
        migrations.AddField(
            model_name='profile',
            name='is_agent',
            field=models.BooleanField(default=False, help_text='Designates whether this user operates as an AI Agent.'),
        ),
        migrations.AddField(
            model_name='profile',
            name='user_type',
            field=models.CharField(choices=[('human', 'Human User / Staff'), ('agent', 'AI Agent Service Account'), ('client', 'External Client / Customer')], default='human', help_text='User classification across the ecosystem.', max_length=20),
        ),
        migrations.AddField(
            model_name='profile',
            name='hermes_profile_name',
            field=models.CharField(blank=True, default='', help_text='Hermes engine profile folder/slug (e.g., cost_controller).', max_length=64),
        ),
        # 3. Alter name to non-unique with default
        migrations.AlterField(
            model_name='profile',
            name='name',
            field=models.CharField(blank=True, default='', help_text='Profile identifier / alias.', max_length=64),
        ),
        # 4. Update user OneToOneField related_name to 'profile'
        migrations.AlterField(
            model_name='profile',
            name='user',
            field=models.OneToOneField(blank=True, help_text='Underlying Django auth.User.', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='profile', to=settings.AUTH_USER_MODEL),
        ),
        # 5. Populate defaults for existing records
        migrations.RunPython(populate_profile_defaults, reverse_code=migrations.RunPython.noop),
    ]
