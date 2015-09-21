# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import datetime
from django.utils.timezone import utc


class Migration(migrations.Migration):

    dependencies = [
        ('openstack', '0010_spl_unique_together_constraint'),
    ]

    operations = [
        migrations.AddField(
            model_name='instance',
            name='last_usage_update_time',
            field=models.DateTimeField(default=datetime.datetime(2015, 9, 21, 10, 33, 39, 68094, tzinfo=utc), auto_now_add=True),
            preserve_default=False,
        ),
    ]
