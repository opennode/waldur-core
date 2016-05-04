# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('cost_tracking', '0019_priceestimate_limit'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='pricelistitem',
            unique_together=set([]),
        ),
        migrations.RemoveField(
            model_name='pricelistitem',
            name='content_type',
        ),
        migrations.RemoveField(
            model_name='pricelistitem',
            name='resource_content_type',
        ),
        migrations.DeleteModel(
            name='PriceListItem',
        ),
    ]
