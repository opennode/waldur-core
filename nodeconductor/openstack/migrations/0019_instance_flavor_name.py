# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('openstack', '0018_instance_tags'),
    ]

    operations = [
        migrations.AddField(
            model_name='instance',
            name='flavor_name',
            field=models.CharField(max_length=255, blank=True),
            preserve_default=True,
        ),
    ]
