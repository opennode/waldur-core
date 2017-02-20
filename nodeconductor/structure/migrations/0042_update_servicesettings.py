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
                ('description', models.CharField(max_length=500, verbose_name='description', blank=True)),
                ('uuid', nodeconductor.core.fields.UUIDField()),
                ('value', models.CharField(max_length=255)),
                ('url', models.URLField(max_length=255, blank=True)),
            ],
            options={
                'verbose_name': 'Certification',
                'verbose_name_plural': 'Certifications',
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
            model_name='servicesettings',
            name='certifications',
            field=models.ManyToManyField(related_name='service_settings', to='structure.Certification'),
        ),
    ]
