# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        # migrations 29 and 30 where deleted.
        ('structure', '0028_servicesettings_service_type2'),
    ]

    operations = [
        migrations.AlterField(
            model_name='servicesettings',
            name='options',
            field=jsonfield.fields.JSONField(default={}, help_text='Extra options'),
            preserve_default=True,
        ),
    ]
