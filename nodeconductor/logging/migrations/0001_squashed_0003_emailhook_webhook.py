# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.utils.timezone
import model_utils.fields
import jsonfield.fields
import django.db.models.deletion
from django.conf import settings
import nodeconductor.core.fields


class Migration(migrations.Migration):

    replaces = [('logging', '0001_initial'), ('logging', '0002_alert_acknowledged'), ('logging', '0003_emailhook_webhook')]

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('contenttypes', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Alert',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, verbose_name='created', editable=False)),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, verbose_name='modified', editable=False)),
                ('uuid', nodeconductor.core.fields.UUIDField()),
                ('alert_type', models.CharField(max_length=50)),
                ('message', models.CharField(max_length=255)),
                ('severity', models.SmallIntegerField(choices=[(10, b'Debug'), (20, b'Info'), (30, b'Warning'), (40, b'Error')])),
                ('closed', models.DateTimeField(null=True, blank=True)),
                ('context', jsonfield.fields.JSONField(blank=True)),
                ('object_id', models.PositiveIntegerField(null=True)),
                ('content_type', models.ForeignKey(on_delete=django.db.models.deletion.SET_NULL, to='contenttypes.ContentType', null=True)),
                ('acknowledged', models.BooleanField(default=False)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='EmailHook',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, verbose_name='created', editable=False)),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, verbose_name='modified', editable=False)),
                ('uuid', nodeconductor.core.fields.UUIDField()),
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
                ('uuid', nodeconductor.core.fields.UUIDField()),
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
