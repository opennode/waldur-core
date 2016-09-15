# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import nodeconductor.core.fields


class Migration(migrations.Migration):

    dependencies = [
        ('cost_tracking', '0019_priceestimate_limit'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='pricelistitem',
            unique_together=set([]),
        ),
        migrations.RemoveField(
            model_name='pricelistitem',
            name='content_type',
        ),
        migrations.RemoveField(
            model_name='pricelistitem',
            name='resource_content_type',
        ),
        migrations.DeleteModel(
            name='PriceListItem',
        ),
        migrations.CreateModel(
            name='PriceListItem',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('uuid', nodeconductor.core.fields.UUIDField()),
                ('value', models.DecimalField(default=0, verbose_name='Hourly rate', max_digits=11, decimal_places=5)),
                ('units', models.CharField(max_length=255, blank=True)),
                ('object_id', models.PositiveIntegerField()),
                ('content_type', models.ForeignKey(to='contenttypes.ContentType')),
                ('default_price_list_item', models.ForeignKey(to='cost_tracking.DefaultPriceListItem')),
            ],
        ),
        migrations.AlterUniqueTogether(
            name='pricelistitem',
            unique_together=set([('content_type', 'object_id', 'default_price_list_item')]),
        ),
    ]
