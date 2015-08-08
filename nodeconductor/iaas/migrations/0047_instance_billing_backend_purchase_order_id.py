# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('iaas', '0046_added_billing_backend_template_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='instance',
            name='billing_backend_purchase_order_id',
            field=models.CharField(help_text=b'ID of a purchase order in backend that created a resource', max_length=255, blank=True),
            preserve_default=True,
        ),
    ]
