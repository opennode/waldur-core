# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import gm2m.fields

from nodeconductor.structure.models import Resource
from nodeconductor.cost_tracking.models import PriceEstimate


def update_price_estimate_relations(apps, schema_editor):
    for model in Resource.get_all_models():
        for resource in model.objects.all():
            PriceEstimate.update_ancessors_for_resource(resource, force=True)


class Migration(migrations.Migration):

    dependencies = [
        ('structure', '__latest__'),
        ('contenttypes', '0001_initial'),
        ('cost_tracking', '0015_defaultpricelistitem_metadata'),
    ]

    operations = [
        migrations.AddField(
            model_name='priceestimate',
            name='consumed',
            field=models.FloatField(default=0),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='priceestimate',
            name='leaf_estimates',
            field=gm2m.fields.GM2MField('cost_tracking.PriceEstimate', through_fields=(b'gm2m_src', b'gm2m_tgt', b'gm2m_ct', b'gm2m_pk')),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='priceestimate',
            name='content_type',
            field=models.ForeignKey(related_name='+', to='contenttypes.ContentType', null=True),
            preserve_default=True,
        ),
        migrations.RunPython(update_price_estimate_relations),
    ]
