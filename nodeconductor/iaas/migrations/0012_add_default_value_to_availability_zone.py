# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('iaas', '0011_cloudprojectmembership_availability_zone'),
    ]

    operations = [
        migrations.AlterField(
            model_name='cloudprojectmembership',
            name='availability_zone',
            field=models.CharField(default='', help_text='Optional availability group. Will be used for all instances provisioned in this tenant', max_length=100, blank=True),
            preserve_default=True,
        ),
    ]
