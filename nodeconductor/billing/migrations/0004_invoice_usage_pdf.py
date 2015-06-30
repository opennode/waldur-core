# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0003_invoice_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='invoice',
            name='usage_pdf',
            field=models.FileField(null=True, upload_to=b'invoices_usage', blank=True),
            preserve_default=True,
        ),
    ]
