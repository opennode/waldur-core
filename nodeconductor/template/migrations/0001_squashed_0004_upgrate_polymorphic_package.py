# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import uuidfield.fields


class Migration(migrations.Migration):

    replaces = [(b'template', '0001_initial'), (b'template', '0002_inherit_namemixin'), (b'template', '0003_rename_tamplate_field'), (b'template', '0004_upgrate_polymorphic_package')]

    dependencies = [
        ('contenttypes', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='Template',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('description', models.CharField(max_length=500, verbose_name='description', blank=True)),
                ('icon_url', models.URLField(verbose_name='icon url', blank=True)),
                ('uuid', uuidfield.fields.UUIDField(unique=True, max_length=32, editable=False, blank=True)),
                ('name', models.CharField(unique=True, max_length=150)),
                ('is_active', models.BooleanField(default=False)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='TemplateService',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=150, verbose_name='name')),
                ('polymorphic_ctype', models.ForeignKey(related_name='polymorphic_template.templateservice_set', editable=False, to='contenttypes.ContentType', null=True)),
                ('base_template', models.ForeignKey(related_name='services', to='template.Template')),
            ],
        ),
        migrations.AlterUniqueTogether(
            name='templateservice',
            unique_together=set([('base_template', 'name', 'polymorphic_ctype')]),
        ),
    ]
