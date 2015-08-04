# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import uuidfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0001_initial'),
        ('cost_tracking', '0002_price_list'),
    ]

    operations = [
        migrations.CreateModel(
            name='DefaultPriceListItem',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('uuid', uuidfield.fields.UUIDField(unique=True, max_length=32, editable=False, blank=True)),
                ('key', models.CharField(max_length=50)),
                ('value', models.DecimalField(default=0, max_digits=16, decimal_places=8)),
                ('units', models.CharField(max_length=30, blank=True)),
                ('item_type', models.CharField(default=b'other', max_length=10, choices=[(b'flavor', b'flavor'), (b'storage', b'storage'), (b'license', b'license'), (b'supported', b'supported'), (b'other', b'other')])),
                ('is_manually_input', models.BooleanField(default=False)),
                ('service_content_type', models.ForeignKey(to='contenttypes.ContentType')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ResourcePriceItem',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('uuid', uuidfield.fields.UUIDField(unique=True, max_length=32, editable=False, blank=True)),
                ('object_id', models.PositiveIntegerField()),
                ('content_type', models.ForeignKey(to='contenttypes.ContentType')),
                ('item', models.ForeignKey(related_name='resource_price_items', to='cost_tracking.PriceListItem')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AlterUniqueTogether(
            name='pricelist',
            unique_together=None,
        ),
        migrations.RemoveField(
            model_name='pricelist',
            name='content_type',
        ),
        migrations.AlterUniqueTogether(
            name='resourcepriceitem',
            unique_together=set([('item', 'content_type', 'object_id')]),
        ),
        migrations.RenameField(
            model_name='priceestimate',
            old_name='is_manually_inputed',
            new_name='is_manually_input',
        ),
        migrations.AddField(
            model_name='pricelistitem',
            name='content_type',
            field=models.ForeignKey(default=1, to='contenttypes.ContentType'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='pricelistitem',
            name='item_type',
            field=models.CharField(default=b'other', max_length=10, choices=[(b'flavor', b'flavor'), (b'storage', b'storage'), (b'license', b'license'), (b'supported', b'supported'), (b'other', b'other')]),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='pricelistitem',
            name='key',
            field=models.CharField(default='test-key', max_length=50),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='pricelistitem',
            name='object_id',
            field=models.PositiveIntegerField(default=1),
            preserve_default=False,
        ),
        migrations.AlterUniqueTogether(
            name='priceestimate',
            unique_together=set([('content_type', 'object_id', 'month', 'year', 'is_manually_input')]),
        ),
        migrations.AlterUniqueTogether(
            name='pricelistitem',
            unique_together=set([('key', 'content_type', 'object_id')]),
        ),
        migrations.RemoveField(
            model_name='pricelistitem',
            name='price_list',
        ),
        migrations.DeleteModel(
            name='PriceList',
        ),
        migrations.RemoveField(
            model_name='pricelistitem',
            name='name',
        ),
    ]
