# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import model_utils.fields
import nodeconductor.core.fields
import nodeconductor.structure.models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('structure', '0037_remove_customer_billing_backend_id'),
    ]

    operations = [
        migrations.CreateModel(
            name='CustomerPermission',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, editable=False)),
                ('expiration_time', models.DateTimeField(null=True, blank=True)),
                ('is_active', models.BooleanField(default=True, db_index=True)),
                ('role', nodeconductor.structure.models.CustomerRole(db_index=True, max_length=30, choices=[('owner', 'Owner')])),
            ],
        ),
        migrations.CreateModel(
            name='ProjectPermission',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('uuid', nodeconductor.core.fields.UUIDField()),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, editable=False)),
                ('expiration_time', models.DateTimeField(null=True, blank=True)),
                ('is_active', models.BooleanField(default=True, db_index=True)),
                ('role', nodeconductor.structure.models.ProjectRole(db_index=True, max_length=30, choices=[('admin', 'Administrator'), ('manager', 'Manager')])),
            ],
        ),
        migrations.AlterUniqueTogether(
            name='customerrole',
            unique_together=set([]),
        ),
        migrations.RemoveField(
            model_name='customerrole',
            name='customer',
        ),
        migrations.RemoveField(
            model_name='customerrole',
            name='permission_group',
        ),
        migrations.RemoveField(
            model_name='projectgroup',
            name='customer',
        ),
        migrations.RemoveField(
            model_name='projectgroup',
            name='projects',
        ),
        migrations.AlterUniqueTogether(
            name='projectgrouprole',
            unique_together=set([]),
        ),
        migrations.RemoveField(
            model_name='projectgrouprole',
            name='permission_group',
        ),
        migrations.RemoveField(
            model_name='projectgrouprole',
            name='project_group',
        ),
        migrations.AlterUniqueTogether(
            name='projectrole',
            unique_together=set([]),
        ),
        migrations.RemoveField(
            model_name='projectrole',
            name='permission_group',
        ),
        migrations.RemoveField(
            model_name='projectrole',
            name='project',
        ),
    ]
