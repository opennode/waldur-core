# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('cost_tracking', '0008_delete_resourceusage'),
    ]

    operations = [
        migrations.AddField(
            model_name='defaultpricelistitem',
            name='name',
            field=models.CharField(default='', max_length=150, verbose_name='name'),
            preserve_default=False,
        ),
    ]
