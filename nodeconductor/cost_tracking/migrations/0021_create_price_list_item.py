# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import uuidfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        ('cost_tracking', '0020_delete_price_list_item'),
    ]

    operations = [
        migrations.CreateModel(
            name='PriceListItem',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('uuid', uuidfield.fields.UUIDField(unique=True, max_length=32, editable=False, blank=True)),
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
