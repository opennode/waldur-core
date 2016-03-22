# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cost_tracking', '0016_leaf_estimates'),
    ]

    operations = [
        migrations.AlterField(
            model_name='priceestimate',
            name='object_id',
            field=models.PositiveIntegerField(null=True),
        ),
    ]
