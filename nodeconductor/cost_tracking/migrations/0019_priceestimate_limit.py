# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('cost_tracking', '0018_priceestimate_threshold'),
    ]

    operations = [
        migrations.AddField(
            model_name='priceestimate',
            name='limit',
            field=models.FloatField(default=-1),
        ),
    ]
