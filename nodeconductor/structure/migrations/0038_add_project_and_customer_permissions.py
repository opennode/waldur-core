# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.conf import settings
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
                ('created_by', models.ForeignKey(related_name='+', blank=True, to=settings.AUTH_USER_MODEL, null=True)),
                ('customer', models.ForeignKey(related_name='permissions', to='structure.Customer')),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
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
                ('created_by', models.ForeignKey(related_name='+', blank=True, to=settings.AUTH_USER_MODEL, null=True)),
                ('project', models.ForeignKey(related_name='permissions', to='structure.Project')),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AlterUniqueTogether(
            name='projectpermission',
            unique_together=set([('project', 'role', 'user', 'is_active')]),
        ),
        migrations.AlterUniqueTogether(
            name='customerpermission',
            unique_together=set([('customer', 'role', 'user', 'is_active')]),
        ),

    ]
