# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('structure', '0016_init_nc_resource_count_quotas'),
    ]

    operations = [
        migrations.AlterField(
            model_name='servicesettings',
            name='type',
            field=models.SmallIntegerField(choices=[(1, b'OpenStack'), (2, b'DigitalOcean'), (3, b'Amazon'), (4, b'Jira'), (5, b'GitLab'), (6, b'Oracle'), (7, b'Azure')]),
            preserve_default=True,
        ),
    ]
