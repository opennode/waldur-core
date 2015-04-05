# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('iaas', '0020_openstacksettings'),
    ]

    operations = [
        migrations.RenameField(
            model_name='instance',
            old_name='hostname',
            new_name='name',
        ),
    ]
