# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('iaas', '0005_auto_20141229_1915'),
    ]

    operations = [
        migrations.AlterField(
            model_name='instance',
            name='cloud_project_membership',
            field=models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.PROTECT, to='iaas.CloudProjectMembership'),
            preserve_default=True,
        ),
    ]
