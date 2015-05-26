# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('structure', '0007_add_service_model'),
    ]

    operations = [
        migrations.AddField(
            model_name='customer',
            name='balance',
            field=models.DecimalField(null=True, max_digits=9, decimal_places=3, blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='customer',
            name='billing_backend_id',
            field=models.CharField(max_length=255, blank=True),
            preserve_default=True,
        ),
    ]
