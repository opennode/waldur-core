# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('structure', '0039_remove_permission_groups'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='customerpermission',
            unique_together=set([]),
        ),
        migrations.AlterUniqueTogether(
            name='projectpermission',
            unique_together=set([]),
        ),
    ]
