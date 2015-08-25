# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('structure', '0017_add_azure_service_type'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='servicesettings',
            options={'verbose_name': 'Service settings', 'verbose_name_plural': 'Service settings'},
        ),
    ]
