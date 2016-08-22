# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('cost_tracking', '0025_priceestimate_parents'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='priceestimate',
            name='leafs',
        ),
        migrations.RemoveField(
            model_name='priceestimate',
            name='scope_customer',
        ),
        migrations.AlterField(
            model_name='priceestimate',
            name='details',
            field=jsonfield.fields.JSONField(help_text='Saved scope details. Field is populated on scope deletion.', blank=True),
        ),
        migrations.AlterField(
            model_name='priceestimate',
            name='parents',
            field=models.ManyToManyField(help_text='Price estimate parents', related_name='children', to='cost_tracking.PriceEstimate'),
        ),
    ]
