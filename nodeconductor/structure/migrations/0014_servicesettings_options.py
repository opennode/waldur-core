# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('structure', '0013_servicesettings_customer'),
    ]

    operations = [
        migrations.AddField(
            model_name='servicesettings',
            name='options',
            field=jsonfield.fields.JSONField(help_text='Extra options', blank=True),
            preserve_default=True,
        ),
    ]
