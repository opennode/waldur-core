# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('openstack', '0026_tenant_runtime_state'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='openstackserviceprojectlink',
            name='availability_zone',
        ),
        migrations.RemoveField(
            model_name='openstackserviceprojectlink',
            name='external_network_id',
        ),
        migrations.RemoveField(
            model_name='openstackserviceprojectlink',
            name='internal_network_id',
        ),
        migrations.RemoveField(
            model_name='openstackserviceprojectlink',
            name='tenant_id',
        ),
    ]
