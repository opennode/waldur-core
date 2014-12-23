# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import uuidfield.fields
import nodeconductor.core.fields


class Migration(migrations.Migration):

    dependencies = [
        ('iaas', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='FloatingIP',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('uuid', uuidfield.fields.UUIDField(unique=True, max_length=32, editable=False, blank=True)),
                ('address', nodeconductor.core.fields.IPsField(max_length=256)),
                ('status', models.CharField(max_length=30)),
                ('backend_id', models.CharField(max_length=255)),
                ('cloud_project_membership', models.ForeignKey(related_name='+', to='iaas.CloudProjectMembership')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
    ]
