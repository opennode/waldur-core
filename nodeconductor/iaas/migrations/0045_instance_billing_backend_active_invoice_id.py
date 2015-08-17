# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('iaas', '0044_floatingip_backend_network_id.py'),
    ]

    operations = [
        migrations.AddField(
            model_name='instance',
            name='billing_backend_active_invoice_id',
            field=models.CharField(help_text=b'ID of an active invoice in backend', max_length=255, blank=True),
            preserve_default=True,
        ),
    ]
