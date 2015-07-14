# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('iaas', '0039_cloudprojectmembership_external_network_id'),
    ]

    operations = [
        migrations.AlterField(
            model_name='cloudprojectmembership',
            name='project',
            field=models.ForeignKey(related_name='+', to='structure.Project'),
            preserve_default=True,
        ),
    ]
