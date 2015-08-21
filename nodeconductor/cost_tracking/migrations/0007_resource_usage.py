# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import uuidfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0001_initial'),
        ('cost_tracking', '0006_add_backend_cache_fields_to_pricelist'),
    ]

    operations = [
        migrations.CreateModel(
            name='ResourceUsage',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('uuid', uuidfield.fields.UUIDField(unique=True, max_length=32, editable=False, blank=True)),
                ('date', models.DateField()),
                ('object_id', models.PositiveIntegerField()),
                ('units', models.CharField(max_length=30, blank=True)),
                ('value', models.DecimalField(default=0, max_digits=16, decimal_places=8)),
                ('content_type', models.ForeignKey(to='contenttypes.ContentType')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
        migrations.AlterUniqueTogether(
            name='resourceusage',
            unique_together=set([('date', 'content_type', 'object_id', 'units')]),
        ),
    ]
