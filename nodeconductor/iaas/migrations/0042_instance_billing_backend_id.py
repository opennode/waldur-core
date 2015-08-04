# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('iaas', '0041_rename_service_models'),
    ]

    operations = [
        migrations.AddField(
            model_name='instance',
            name='billing_backend_id',
            field=models.CharField(max_length=255, blank=True),
            preserve_default=True,
        ),
    ]
