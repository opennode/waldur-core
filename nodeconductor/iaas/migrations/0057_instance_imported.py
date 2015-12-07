# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('iaas', '0056_instance_tags'),
    ]

    operations = [
        migrations.AddField(
            model_name='instance',
            name='imported',
            field=models.BooleanField(default=False, help_text='Was it imported or created', editable=False),
            preserve_default=True,
        ),
    ]
