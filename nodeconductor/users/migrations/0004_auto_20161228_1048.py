# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import nodeconductor.structure.models


class Migration(migrations.Migration):

    dependencies = [
        ('structure', '0038_auto_20161228_1048'),
        ('users', '0003_invitation_civil_number'),
    ]

    operations = [
        migrations.AddField(
            model_name='invitation',
            name='project',
            field=models.ForeignKey(related_name='invitations', blank=True, to='structure.Project', null=True),
        ),
        migrations.AlterField(
            model_name='invitation',
            name='customer_role',
            field=nodeconductor.structure.models.CustomerRole(blank=True, max_length=30, null=True, choices=[('owner', 'Owner')]),
        ),
        migrations.AlterField(
            model_name='invitation',
            name='project_role',
            field=nodeconductor.structure.models.ProjectRole(blank=True, max_length=30, null=True, choices=[('admin', 'Administrator'), ('manager', 'Manager')]),
        ),
    ]
