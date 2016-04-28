# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('openstack', '0029_auto_20160428_0927'),
    ]

    operations = [
        migrations.RenameField(
            model_name='tenant',
            old_name='admin_password',
            new_name='user_password',
        ),
        migrations.RenameField(
            model_name='tenant',
            old_name='admin_username',
            new_name='user_username',
        ),
    ]
