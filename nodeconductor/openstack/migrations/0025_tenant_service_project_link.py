# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('openstack', '0024_tenant'),
    ]

    operations = [
        migrations.AddField(
            model_name='tenant',
            name='service_project_link',
            field=models.ForeignKey(related_name='tenants', on_delete=django.db.models.deletion.PROTECT, default=1, to='openstack.OpenStackServiceProjectLink'),
            preserve_default=False,
        ),
    ]
