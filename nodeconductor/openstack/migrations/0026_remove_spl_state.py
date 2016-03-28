# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('openstack', '0025_init_spl_tenants'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='openstackserviceprojectlink',
            name='error_message',
        ),
        migrations.RemoveField(
            model_name='openstackserviceprojectlink',
            name='state',
        ),
    ]
