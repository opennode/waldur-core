# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import uuidfield.fields
import django_fsm

import nodeconductor.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('structure', '0008_add_customer_billing_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='ServiceSettings',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=150, verbose_name='name', validators=[nodeconductor.core.validators.validate_name])),
                ('uuid', uuidfield.fields.UUIDField(unique=True, max_length=32, editable=False, blank=True)),
                ('state', django_fsm.FSMIntegerField(default=1, choices=[(1, 'Sync Scheduled'), (2, 'Syncing'), (3, 'In Sync'), (4, 'Erred')])),
                ('backend_url', models.URLField(null=True, blank=True)),
                ('username', models.CharField(max_length=100, null=True, blank=True)),
                ('password', models.CharField(max_length=100, null=True, blank=True)),
                ('token', models.CharField(max_length=255, null=True, blank=True)),
                ('type', models.SmallIntegerField(choices=[(1, 'OpenStack'), (2, 'DigitalOcean'), (3, 'Amazon'), (4, 'Jira'), (5, 'GitLab')])),
                ('shared', models.BooleanField(default=False, help_text='Anybody can use it')),
                ('dummy', models.BooleanField(default=False, help_text='Emulate backend operations')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.RemoveField(
            model_name='service',
            name='dummy',
        ),
        migrations.RemoveField(
            model_name='service',
            name='state',
        ),
        migrations.AddField(
            model_name='service',
            name='settings',
            field=models.ForeignKey(related_name='+', to='structure.ServiceSettings'),
            preserve_default=False,
        ),
    ]
