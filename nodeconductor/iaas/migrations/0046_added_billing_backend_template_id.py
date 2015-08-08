# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('iaas', '0045_extend_template_os_and_application_types'),
    ]

    operations = [
        migrations.AddField(
            model_name='instance',
            name='billing_backend_template_id',
            field=models.CharField(help_text=b'ID of a template in backend used for creating a resource', max_length=255, blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='instance',
            name='billing_backend_id',
            field=models.CharField(help_text=b'ID of a resource in backend', max_length=255, blank=True),
            preserve_default=True,
        ),
    ]
