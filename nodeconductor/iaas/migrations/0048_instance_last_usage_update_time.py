# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import datetime
from django.utils import timezone
from django.utils.timezone import utc


def set_last_usage_update_time(apps, schema_editor):
    Instance = apps.get_model('iaas', 'Instance')
    now = timezone.now()
    if now.minute > 10:
        Instance.objects.all().update(last_usage_update_time=now.replace(minute=10))
    else:
        Instance.objects.all().update(last_usage_update_time=now.replace(minute=10) - datetime.timedelta(hours=1))


class Migration(migrations.Migration):

    dependencies = [
        ('iaas', '0047_refactor_application_type_field'),
    ]

    operations = [
        migrations.AddField(
            model_name='instance',
            name='last_usage_update_time',
            field=models.DateTimeField(default=datetime.datetime(2015, 9, 21, 7, 48, 17, 947642, tzinfo=utc), auto_now_add=True),
            preserve_default=False,
        ),
        migrations.RunPython(set_last_usage_update_time),
    ]
