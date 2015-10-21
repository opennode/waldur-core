# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django_fsm


class Migration(migrations.Migration):

    dependencies = [
        ('iaas', '0049_add_creation_states'),
    ]

    operations = [
        migrations.AlterField(
            model_name='cloudprojectmembership',
            name='state',
            field=django_fsm.FSMIntegerField(default=1, choices=[(0, 'New'), (5, 'Creation Scheduled'), (6, 'Creating'), (1, 'Sync Scheduled'), (2, 'Syncing'), (3, 'In Sync'), (4, 'Erred')]),
            preserve_default=True,
        ),
    ]
