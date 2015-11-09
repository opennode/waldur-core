# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('iaas', '0051_instanceslahistory_verbose_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='cloud',
            name='error_message',
            field=models.TextField(blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='cloudprojectmembership',
            name='error_message',
            field=models.TextField(blank=True),
            preserve_default=True,
        ),
        migrations.AddField(
            model_name='securitygroup',
            name='error_message',
            field=models.TextField(blank=True),
            preserve_default=True,
        ),
    ]
