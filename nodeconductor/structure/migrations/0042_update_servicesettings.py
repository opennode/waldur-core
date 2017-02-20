# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import nodeconductor.core.fields


class Migration(migrations.Migration):

    dependencies = [
        ('structure', '0041_servicesettings_domain'),
    ]

    operations = [
        migrations.CreateModel(
            name='Certification',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('uuid', nodeconductor.core.fields.UUIDField()),
                ('value', models.CharField(max_length=255)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.AddField(
            model_name='servicesettings',
            name='homepage',
            field=models.URLField(max_length=255, blank=True),
        ),
        migrations.AddField(
            model_name='servicesettings',
            name='terms_of_services',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='certification',
            name='service_settings',
            field=models.ManyToManyField(related_name='certifications', to='structure.ServiceSettings'),
        ),
        migrations.AddField(
            model_name='certification',
            name='description',
            field=models.CharField(max_length=500, verbose_name='description', blank=True),
        ),
        migrations.AddField(
            model_name='certification',
            name='url',
            field=models.URLField(max_length=255, blank=True),
        ),
    ]
