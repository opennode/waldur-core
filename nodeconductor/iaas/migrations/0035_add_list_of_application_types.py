# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('iaas', '0034_instance_installation_state'),
    ]

    operations = [
        migrations.AlterField(
            model_name='template',
            name='application_type',
            field=models.CharField(default='None', help_text='Type of the application inside the template (optional)', max_length=100, blank=True, choices=[('WordPress', 'WordPress'), ('PostgreSQL', 'PostgreSQL'), ('Zimbra', 'Zimbra'), ('None', 'None')]),
            preserve_default=True,
        ),
    ]
