# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import nodeconductor.core.fields
import nodeconductor.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('structure', '0041_servicesettings_domain'),
    ]

    operations = [
        migrations.CreateModel(
            name='ServiceCertification',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('description', models.CharField(max_length=500, verbose_name='description', blank=True)),
                ('name', models.CharField(max_length=150, verbose_name='name', validators=[nodeconductor.core.validators.validate_name])),
                ('uuid', nodeconductor.core.fields.UUIDField()),
                ('link', models.URLField(max_length=255, blank=True)),
            ],
            options={
                'ordering': ['-name'],
                'verbose_name': 'Service Certification',
                'verbose_name_plural': 'Service Certifications',
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
            field=models.ManyToManyField(blank=True, related_name='service_settings', to='structure.ServiceCertification'),
        ),
    ]
