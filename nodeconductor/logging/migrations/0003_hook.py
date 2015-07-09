# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import jsonfield.fields
import django.utils.timezone
from django.conf import settings
import model_utils.fields
import uuidfield.fields


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('logging', '0002_alert_acknowledged'),
    ]

    operations = [
        migrations.CreateModel(
            name='Hook',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, verbose_name='created', editable=False)),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, verbose_name='modified', editable=False)),
                ('uuid', uuidfield.fields.UUIDField(unique=True, max_length=32, editable=False, blank=True)),
                ('is_active', models.BooleanField(default=True)),
                ('events', jsonfield.fields.JSONField(verbose_name=b'List of event types')),
                ('name', models.CharField(max_length=50, verbose_name=b'Name of publishing service', choices=[(b'web', b'web'), (b'email', b'email')])),
                ('settings', jsonfield.fields.JSONField(verbose_name=b'Settings of publishing service')),
                ('last_published', models.DateTimeField(default=django.utils.timezone.now, blank=True)),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
    ]
