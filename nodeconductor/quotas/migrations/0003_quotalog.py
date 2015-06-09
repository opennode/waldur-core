# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.utils.timezone
import model_utils.fields


class Migration(migrations.Migration):

    dependencies = [
        ('quotas', '0002_inherit_namemixin'),
    ]

    operations = [
        migrations.CreateModel(
            name='QuotaLog',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('limit', models.FloatField(default=-1)),
                ('usage', models.FloatField(default=0)),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, editable=False)),
                ('quota', models.ForeignKey(related_name='items', to='quotas.Quota')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
