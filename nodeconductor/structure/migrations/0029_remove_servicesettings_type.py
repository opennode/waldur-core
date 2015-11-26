# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('structure', '0028_convert_service_type'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='servicesettings',
            name='type',
        ),
        migrations.RenameField(
            model_name='servicesettings',
            old_name='service_type',
            new_name='type'
        )
    ]
