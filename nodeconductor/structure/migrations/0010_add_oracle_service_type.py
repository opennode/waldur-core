# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('structure', '0009_update_service_models'),
    ]

    operations = [
        migrations.AlterField(
            model_name='servicesettings',
            name='type',
            field=models.SmallIntegerField(choices=[(1, 'OpenStack'), (2, 'DigitalOcean'), (3, 'Amazon'), (4, 'Jira'), (5, 'GitLab'), (6, 'Oracle')]),
            preserve_default=True,
        ),
    ]
