# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0005_payment'),
    ]

    operations = [
        migrations.DeleteModel(
            name='PriceList',
        ),
        migrations.RemoveField(
            model_name='invoice',
            name='status',
        ),
        migrations.RemoveField(
            model_name='invoice',
            name='usage_pdf',
        ),
    ]
