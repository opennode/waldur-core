# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('cost_tracking', '0004_remove_connection_to_resource'),
    ]

    operations = [
        migrations.AlterField(
            model_name='defaultpricelistitem',
            name='item_type',
            field=models.CharField(default=b'flavor', max_length=30, choices=[(b'flavor', b'flavor'), (b'storage', b'storage'), (b'license-application', b'license-application'), (b'license-os', b'license-os'), (b'support', b'support'), (b'network', b'network')]),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='pricelistitem',
            name='item_type',
            field=models.CharField(default=b'flavor', max_length=30, choices=[(b'flavor', b'flavor'), (b'storage', b'storage'), (b'license-application', b'license-application'), (b'license-os', b'license-os'), (b'support', b'support'), (b'network', b'network')]),
            preserve_default=True,
        ),
    ]
