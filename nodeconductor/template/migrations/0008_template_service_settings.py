# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('structure', '0028_servicesettings_service_type2'),
        ('template', '0007_template_tags'),
    ]

    operations = [
        migrations.AddField(
            model_name='template',
            name='service_settings',
            field=models.ForeignKey(related_name='templates', to='structure.ServiceSettings', null=True),
            preserve_default=True,
        ),
    ]
