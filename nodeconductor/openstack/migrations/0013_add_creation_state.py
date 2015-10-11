# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django_fsm


class Migration(migrations.Migration):

    dependencies = [
        ('openstack', '0012_create_spl_floating_ip_quota'),
    ]

    operations = [
        migrations.AlterField(
            model_name='openstackserviceprojectlink',
            name='state',
            field=django_fsm.FSMIntegerField(default=5, choices=[(5, 'Creation Scheduled'), (6, 'Creating'), (1, 'Sync Scheduled'), (2, 'Syncing'), (3, 'In Sync'), (4, 'Erred')]),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='securitygroup',
            name='state',
            field=django_fsm.FSMIntegerField(default=1, choices=[(5, 'Creation Scheduled'), (6, 'Creating'), (1, 'Sync Scheduled'), (2, 'Syncing'), (3, 'In Sync'), (4, 'Erred')]),
            preserve_default=True,
        ),
    ]
