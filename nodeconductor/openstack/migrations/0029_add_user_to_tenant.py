# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('openstack', '0028_instance_flavor_disk'),
    ]

    operations = [
        migrations.AddField(
            model_name='tenant',
            name='user_password',
            field=models.CharField(max_length=50, blank=True),
        ),
        migrations.AddField(
            model_name='tenant',
            name='user_username',
            field=models.CharField(max_length=50, blank=True),
        ),
    ]
