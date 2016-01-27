# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('cost_tracking', '0014_more_digits_for_price'),
    ]

    operations = [
        migrations.AddField(
            model_name='defaultpricelistitem',
            name='metadata',
            field=jsonfield.fields.JSONField(blank=True, default='""'),
            preserve_default=False,
        ),
    ]
