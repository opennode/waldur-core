# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_user_organization_approved'),
    ]

    operations = [
        migrations.AlterField(
            model_name='sshpublickey',
            name='name',
            field=models.CharField(max_length=150, blank=True),
            preserve_default=True,
        ),
    ]
