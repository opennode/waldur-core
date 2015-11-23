# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import jsonfield.fields
import django.utils.timezone
import uuidfield.fields
import model_utils.fields


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0001_initial'),
        ('template', '0004_upgrate_polymorphic_package'),
    ]

    operations = [
        migrations.DeleteModel(
            name='TemplateService',
        ),
        migrations.DeleteModel(
            name='Template',
        ),
        migrations.CreateModel(
            name='Template',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('uuid', uuidfield.fields.UUIDField(unique=True, max_length=32, editable=False, blank=True)),
                ('options', jsonfield.fields.JSONField(default={}, help_text=b'Default options for resource provision request.')),
                ('order_number', models.PositiveSmallIntegerField(default=1, help_text=b'Templates in group are sorted by order number. Template with smaller order number will be executed first.')),
                ('use_previous_resource_project', models.BooleanField(default=False, help_text=b'If True and project is not defined in template - current resource will use the same project as previous created.')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='TemplateGroup',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('description', models.CharField(max_length=500, verbose_name='description', blank=True)),
                ('icon_url', models.URLField(verbose_name='icon url', blank=True)),
                ('uuid', uuidfield.fields.UUIDField(unique=True, max_length=32, editable=False, blank=True)),
                ('name', models.CharField(unique=True, max_length=150)),
                ('is_active', models.BooleanField(default=True)),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='TemplateGroupResult',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, verbose_name='created', editable=False)),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, verbose_name='modified', editable=False)),
                ('uuid', uuidfield.fields.UUIDField(unique=True, max_length=32, editable=False, blank=True)),
                ('is_finished', models.BooleanField(default=False)),
                ('is_erred', models.BooleanField(default=False)),
                ('provisioned_resources', jsonfield.fields.JSONField(default={})),
                ('state_message', models.CharField(help_text=b'Human readable description of current state of execution process.', max_length=255, blank=True)),
                ('error_message', models.CharField(help_text=b'Human readable description of error.', max_length=255, blank=True)),
                ('error_details', models.TextField(help_text=b'Error technical details.', blank=True)),
                ('group', models.ForeignKey(related_name='results', to='template.TemplateGroup')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.AddField(
            model_name='template',
            name='group',
            field=models.ForeignKey(related_name='templates', to='template.TemplateGroup'),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='template',
            name='resource_content_type',
            field=models.ForeignKey(help_text=b'Content type of resource which provision process is described in template.', to='contenttypes.ContentType'),
            preserve_default=True,
        ),
    ]
