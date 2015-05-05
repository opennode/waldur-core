# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('iaas', '0029_instance_user_data'),
    ]

    operations = [
        migrations.AddField(
            model_name='template',
            name='application_type',
            field=models.CharField(help_text='Type of the application inside the template (optional)', max_length=100, blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='template',
            name='type',
            field=models.CharField(help_text='Template type', max_length=100, blank=True),
            preserve_default=True,
        ),
    ]
