# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.conf import settings
from django.core.management import call_command

from trusts import ENTITY_MODEL_NAME, PERMISSION_MODEL_NAME, DEFAULT_SETTLOR, ALLOW_NULL_SETTLOR, ROOT_PK
import trusts.models


def forward(apps, schema_editor):
    if getattr(settings, 'TRUSTS_CREATE_ROOT', True):
        call_command('create_trust_root', apps=apps)


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0006_require_contenttypes_0002'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Trust',
            fields=[
                ('id', models.AutoField(verbose_name='ID', auto_created=True, primary_key=True, serialize=False)),
                ('title', models.CharField(verbose_name='title', max_length=40)),
                ('groups', models.ManyToManyField(blank=True, related_name='trusts', verbose_name='groups', to='auth.Group', help_text='The groups this trust grants permissions to. A user willget all permissions granted to each of his/her group.')),
                ('settlor', models.ForeignKey(to=ENTITY_MODEL_NAME, default=DEFAULT_SETTLOR, null=ALLOW_NULL_SETTLOR)),
                ('trust', models.ForeignKey(to='trusts.Trust', related_name='trusts_trust_content', default=ROOT_PK)),
            ],
            options={
                'default_permissions': ('add', 'change', 'delete', 'read'),
            },
            bases=(trusts.models.ReadonlyFieldsMixin, models.Model),
        ),
        migrations.CreateModel(
            name='TrustUserPermission',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, verbose_name='ID', serialize=False)),
                ('entity', models.ForeignKey(to=ENTITY_MODEL_NAME, related_name='trustpermissions')),
                ('permission', models.ForeignKey(to=PERMISSION_MODEL_NAME, related_name='trustentities')),
                ('trust', models.ForeignKey(to='trusts.Trust', related_name='trustees')),
            ],
        ),
        migrations.AlterUniqueTogether(
            name='trust',
            unique_together=set([('settlor', 'title')]),
        ),
        migrations.AlterUniqueTogether(
            name='trustuserpermission',
            unique_together=set([('trust', 'entity', 'permission')]),
        ),
        migrations.RunPython(forward)
    ]
