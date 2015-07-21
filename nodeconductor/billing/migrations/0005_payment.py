# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import model_utils.fields
import django.utils.timezone
import nodeconductor.logging.log
import django_fsm
import uuidfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('structure', '0015_drop_service_polymorphic'),
        ('billing', '0004_invoice_usage_pdf'),
    ]

    operations = [
        migrations.CreateModel(
            name='Payment',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, verbose_name='created', editable=False)),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, verbose_name='modified', editable=False)),
                ('uuid', uuidfield.fields.UUIDField(unique=True, max_length=32, editable=False, blank=True)),
                ('state', django_fsm.FSMIntegerField(default=0, choices=[(0, b'Initial'), (1, b'Created'), (2, b'Approved'), (4, b'Erred')])),
                ('amount', models.DecimalField(max_digits=9, decimal_places=2)),
                ('backend_id', models.CharField(max_length=255, null=True)),
                ('approval_url', models.URLField()),
                ('customer', models.ForeignKey(to='structure.Customer')),
            ],
            options={
                'abstract': False,
            },
            bases=(nodeconductor.logging.log.LoggableMixin, models.Model),
        ),
    ]
