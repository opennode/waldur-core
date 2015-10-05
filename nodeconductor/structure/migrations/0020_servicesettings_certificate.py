# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('structure', '0019_rename_nc_service_count_to_nc_service_project_link_count'),
    ]

    operations = [
        migrations.AddField(
            model_name='servicesettings',
            name='certificate',
            field=models.FileField(null=True, upload_to='certs', blank=True),
            preserve_default=True,
        ),
    ]
