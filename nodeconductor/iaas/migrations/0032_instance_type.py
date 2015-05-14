# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('iaas', '0031_fix_iaas_template_service'),
    ]

    operations = [
        migrations.AddField(
            model_name='instance',
            name='type',
            field=models.CharField(default='IaaS', max_length=10, choices=[('IaaS', 'IaaS'), ('PaaS', 'PaaS')]),
            preserve_default=True,
        ),
    ]
