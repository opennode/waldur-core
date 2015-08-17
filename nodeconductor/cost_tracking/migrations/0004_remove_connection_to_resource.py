# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('cost_tracking', '0003_new_price_list_items'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='resourcepriceitem',
            unique_together=None,
        ),
        migrations.RemoveField(
            model_name='resourcepriceitem',
            name='content_type',
        ),
        migrations.RemoveField(
            model_name='resourcepriceitem',
            name='item',
        ),
        migrations.DeleteModel(
            name='ResourcePriceItem',
        ),
        migrations.RemoveField(
            model_name='defaultpricelistitem',
            name='is_manually_input',
        ),
        migrations.AddField(
            model_name='pricelistitem',
            name='is_manually_input',
            field=models.BooleanField(default=False),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='defaultpricelistitem',
            name='item_type',
            field=models.CharField(default=b'flavor', max_length=10, choices=[(b'flavor', b'flavor'), (b'storage', b'storage'), (b'license-application', b'license-application'), (b'license-os', b'license-os'), (b'support', b'support'), (b'network', b'network')]),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='pricelistitem',
            name='item_type',
            field=models.CharField(default=b'flavor', max_length=10, choices=[(b'flavor', b'flavor'), (b'storage', b'storage'), (b'license-application', b'license-application'), (b'license-os', b'license-os'), (b'support', b'support'), (b'network', b'network')]),
            preserve_default=True,
        ),
    ]
