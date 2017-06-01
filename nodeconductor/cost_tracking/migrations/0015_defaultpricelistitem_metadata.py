# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import nodeconductor.core.fields


class Migration(migrations.Migration):

    dependencies = [
        ('cost_tracking', '0014_more_digits_for_price'),
    ]

    operations = [
        migrations.AddField(
            model_name='defaultpricelistitem',
            name='metadata',
            field=nodeconductor.core.fields.JSONField(blank=True, default={}, help_text='Details of the item, that corresponds price list item. Example: details of flavor.'),
            preserve_default=False,
        ),
    ]
