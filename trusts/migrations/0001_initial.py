# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
from django.conf import settings
from django.core.management import call_command

from trusts import ENTITY_MODEL_NAME, DEFAULT_SETTLOR
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
                ('id', models.AutoField(serialize=False, primary_key=True)),
                ('title', models.CharField(verbose_name='title', max_length=40)),
                ('groups', models.ManyToManyField(blank=True, related_name='trusts', verbose_name='groups', to='auth.Group', help_text='The groups this trust grants permissions to. A user willget all permissions granted to each of his/her group.')),
                ('settlor', models.ForeignKey(to=ENTITY_MODEL_NAME, default=DEFAULT_SETTLOR)),
                ('trust', models.ForeignKey(to='trusts.Trust', related_name='content', default=1)),
                ('trustees', models.ManyToManyField(blank=True, related_name='trusts', verbose_name='trustees', to=ENTITY_MODEL_NAME, help_text='Specific trustees for this trust.')),
            ],
            options={
                'default_permissions': ('add', 'change', 'delete', 'read'),
            },
            bases=(trusts.models.ReadonlyFieldsMixin, models.Model),
        ),
        migrations.AlterUniqueTogether(
            name='trust',
            unique_together=set([('settlor', 'title')]),
        ),
        migrations.RunPython(forward)
    ]
