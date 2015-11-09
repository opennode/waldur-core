# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('openstack', '0015_unique_backend_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='openstackserviceprojectlink',
            name='error_message',
            field=models.TextField(blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='securitygroup',
            name='error_message',
            field=models.TextField(blank=True),
            preserve_default=True,
        ),
    ]
