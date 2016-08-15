# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


def init_leafs(apps, schema_editor):
    PriceEstimate = apps.get_model('cost_tracking', 'PriceEstimate')
    for estimate in PriceEstimate.objects.all():
        for leaf in estimate.leaf_estimates.all():
            estimate.leafs.add(PriceEstimate.objects.get(pk=leaf.pk))


class Migration(migrations.Migration):

    dependencies = [
        ('cost_tracking', '0021_delete_applicationtype'),
    ]

    operations = [
        migrations.AddField(
            model_name='priceestimate',
            name='leafs',
            field=models.ManyToManyField(related_name='_priceestimate_leafs_+', to='cost_tracking.PriceEstimate'),
        ),
        migrations.RunPython(init_leafs),
        migrations.RemoveField(
            model_name='priceestimate',
            name='leaf_estimates',
        ),
    ]
