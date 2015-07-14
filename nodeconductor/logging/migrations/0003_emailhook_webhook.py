# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import model_utils.fields
import jsonfield.fields
import django.utils.timezone
from django.conf import settings
import uuidfield.fields


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('logging', '0002_alert_acknowledged'),
    ]

    operations = [
        migrations.CreateModel(
            name='EmailHook',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, verbose_name='created', editable=False)),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, verbose_name='modified', editable=False)),
                ('uuid', uuidfield.fields.UUIDField(unique=True, max_length=32, editable=False, blank=True)),
                ('event_types', jsonfield.fields.JSONField(verbose_name=b'List of event types')),
                ('is_active', models.BooleanField(default=True)),
                ('last_published', models.DateTimeField(default=django.utils.timezone.now)),
                ('email', models.EmailField(max_length=75)),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='WebHook',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, verbose_name='created', editable=False)),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, verbose_name='modified', editable=False)),
                ('uuid', uuidfield.fields.UUIDField(unique=True, max_length=32, editable=False, blank=True)),
                ('event_types', jsonfield.fields.JSONField(verbose_name=b'List of event types')),
                ('is_active', models.BooleanField(default=True)),
                ('last_published', models.DateTimeField(default=django.utils.timezone.now)),
                ('destination_url', models.URLField()),
                ('content_type', models.SmallIntegerField(default=1, choices=[(1, b'json'), (2, b'form')])),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
    ]
