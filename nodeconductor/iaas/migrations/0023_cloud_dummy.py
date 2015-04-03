# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('iaas', '0022_extend_iaas_template_with_type_icon_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='cloud',
            name='dummy',
            field=models.BooleanField(default=False),
            preserve_default=True,
        ),
    ]
