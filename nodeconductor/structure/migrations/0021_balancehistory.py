# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.utils.timezone
import model_utils.fields


class Migration(migrations.Migration):

    dependencies = [
        ('structure', '0020_servicesettings_certificate'),
    ]

    operations = [
        migrations.CreateModel(
            name='BalanceHistory',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, editable=False)),
                ('amount', models.DecimalField(max_digits=9, decimal_places=3)),
                ('customer', models.ForeignKey(to='structure.Customer')),
            ],
            options={
            },
            bases=(models.Model,),
        ),
    ]
