# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='organization_approved',
            field=models.BooleanField(default=False, help_text='Designates whether user organization was approved.', verbose_name='organization approved'),
            preserve_default=True,
        ),
    ]
