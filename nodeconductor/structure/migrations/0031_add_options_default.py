# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('structure', '0030_customer_app_vm_count'),
    ]

    operations = [
        migrations.AlterField(
            model_name='servicesettings',
            name='options',
            field=jsonfield.fields.JSONField(default={}, help_text='Extra options'),
            preserve_default=True,
        ),
    ]
