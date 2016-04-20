# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('template', '0008_template_service_settings'),
    ]

    operations = [
        migrations.RenameField(
            model_name='template',
            old_name='resource_content_type',
            new_name='object_content_type',
        ),
        migrations.RenameField(
            model_name='template',
            old_name='use_previous_project',
            new_name='use_previous_project',
        ),
    ]
