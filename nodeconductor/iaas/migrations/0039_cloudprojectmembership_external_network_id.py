# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('iaas', '0038_securitygroup_state'),
    ]

    operations = [
        migrations.AddField(
            model_name='cloudprojectmembership',
            name='external_network_id',
            field=models.CharField(max_length=64, blank=True),
            preserve_default=True,
        ),
    ]
