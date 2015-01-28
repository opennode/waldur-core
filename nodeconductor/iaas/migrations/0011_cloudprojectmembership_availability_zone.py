# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('iaas', '0010_auto_20150118_1834'),
    ]

    operations = [
        migrations.AddField(
            model_name='cloudprojectmembership',
            name='availability_zone',
            field=models.CharField(help_text='Optional availability group. Will be used for all instances provisioned in this tenant', max_length=100, blank=True, default=''),
            preserve_default=False,
        ),
    ]
