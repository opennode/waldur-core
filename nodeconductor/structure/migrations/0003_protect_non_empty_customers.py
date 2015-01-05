# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('structure', '0002_customer_native_name'),
    ]

    operations = [
        migrations.AlterField(
            model_name='project',
            name='customer',
            field=models.ForeignKey(related_name='projects', on_delete=django.db.models.deletion.PROTECT, to='structure.Customer'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='projectgroup',
            name='customer',
            field=models.ForeignKey(related_name='project_groups', on_delete=django.db.models.deletion.PROTECT, to='structure.Customer'),
            preserve_default=True,
        ),
    ]
