# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('iaas', '0027_refactor_cron_schedule_field'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='cloudprojectmembership',
            unique_together=set([('cloud', 'project')]),
        ),
    ]
