# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import django.core.validators
from django.db import models, migrations
import django.utils.timezone
import model_utils.fields
import uuidfield.fields


class Migration(migrations.Migration):
    dependencies = [
        ('auth', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Customer',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('uuid', uuidfield.fields.UUIDField(unique=True, max_length=32, editable=False, blank=True)),
                ('created',
                 model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, verbose_name='created',
                                                     editable=False)),
                ('modified',
                 model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, verbose_name='modified',
                                                          editable=False)),
                ('name', models.CharField(max_length=160)),
                ('abbreviation', models.CharField(max_length=8, blank=True)),
                ('contact_details',
                 models.TextField(blank=True, validators=[django.core.validators.MaxLengthValidator(500)])),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='CustomerRole',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('role_type', models.SmallIntegerField(choices=[(0, 'Owner')])),
                ('customer', models.ForeignKey(related_name='roles', to='structure.Customer')),
                ('permission_group', models.OneToOneField(to='auth.Group')),
            ],
            options={
                'unique_together': set([('customer', 'role_type')]),
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='Project',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('description', models.CharField(max_length=500, blank=True, verbose_name='description')),
                ('uuid', uuidfield.fields.UUIDField(unique=True, max_length=32, editable=False, blank=True)),
                ('created',
                 model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, verbose_name='created',
                                                     editable=False)),
                ('modified',
                 model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, verbose_name='modified',
                                                          editable=False)),
                ('name', models.CharField(max_length=80)),
                ('customer', models.ForeignKey(related_name='projects', to='structure.Customer')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ProjectRole',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('uuid', uuidfield.fields.UUIDField(unique=True, max_length=32, editable=False, blank=True)),
                ('role_type', models.SmallIntegerField(choices=[(0, 'Administrator'), (1, 'Manager')])),
                ('permission_group', models.OneToOneField(to='auth.Group')),
                ('project', models.ForeignKey(related_name='roles', to='structure.Project')),
            ],
            options={
                'unique_together': set([('project', 'role_type')]),
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ProjectGroup',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('description', models.CharField(max_length=500, blank=True, verbose_name='description')),
                ('uuid', uuidfield.fields.UUIDField(unique=True, max_length=32, editable=False, blank=True)),
                ('created',
                 model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, verbose_name='created',
                                                     editable=False)),
                ('modified',
                 model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, verbose_name='modified',
                                                          editable=False)),
                ('name', models.CharField(max_length=80)),
                ('customer', models.ForeignKey(related_name='project_groups', to='structure.Customer')),
                ('projects', models.ManyToManyField(related_name='project_groups', to='structure.Project')),
            ],
            options={
                'abstract': False,
            },
            bases=(models.Model,),
        ),
        migrations.CreateModel(
            name='ProjectGroupRole',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('uuid', uuidfield.fields.UUIDField(unique=True, max_length=32, editable=False, blank=True)),
                ('role_type', models.SmallIntegerField(choices=[(0, 'Group Manager')])),
                ('permission_group', models.OneToOneField(to='auth.Group')),
                ('project_group', models.ForeignKey(related_name='roles', to='structure.ProjectGroup')),
            ],
            options={
                'unique_together': set([('project_group', 'role_type')]),
            },
            bases=(models.Model,),
        ),
    ]
