# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('structure', '0010_add_oracle_service_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='customer',
            name='registration_code',
            field=models.CharField(default='', max_length=160, blank=True),
            preserve_default=True,
        ),
    ]
