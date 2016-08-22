# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cost_tracking', '0024_auto_20160818_1003'),
    ]

    operations = [
        migrations.AddField(
            model_name='priceestimate',
            name='parents',
            field=models.ManyToManyField(related_name='children', to='cost_tracking.PriceEstimate'),
        ),
    ]
