# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('iaas', '0043_enhance_resource_and_template_for_billing'),
    ]

    operations = [
        migrations.AddField(
            model_name='floatingip',
            name='backend_network_id',
            field=models.CharField(default='', max_length=255, editable=False),
            preserve_default=False,
        ),
    ]
