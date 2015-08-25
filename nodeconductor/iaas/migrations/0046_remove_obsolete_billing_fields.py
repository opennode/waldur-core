# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('iaas', '0045_instance_billing_backend_active_invoice_id'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='instance',
            name='billing_backend_active_invoice_id',
        ),
        migrations.RemoveField(
            model_name='instance',
            name='billing_backend_purchase_order_id',
        ),
        migrations.RemoveField(
            model_name='instance',
            name='billing_backend_template_id',
        ),
    ]
