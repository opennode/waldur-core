# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('iaas', '0042_instance_billing_backend_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='instance',
            name='flavor_name',
            field=models.CharField(max_length=255, blank=True),
            preserve_default=True,
        ),
    ]
