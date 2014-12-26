# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('iaas', '0002_floatingip'),
    ]

    operations = [
        migrations.AlterField(
            model_name='floatingip',
            name='address',
            field=models.GenericIPAddressField(protocol='IPv4'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='instance',
            name='external_ips',
            field=models.GenericIPAddressField(null=True, protocol='IPv4', blank=True),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='instance',
            name='internal_ips',
            field=models.GenericIPAddressField(null=True, protocol='IPv4', blank=True),
            preserve_default=True,
        ),
    ]
