# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('iaas', '0040_update_cloudprojectmembership'),
    ]

    operations = [
        migrations.AlterField(
            model_name='cloudprojectmembership',
            name='project',
            field=models.ForeignKey(to='structure.Project'),
            preserve_default=True,
        ),
    ]
