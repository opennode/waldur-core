# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('quotas', '0001_initial'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='quota',
            unique_together=set([('name', 'content_type', 'object_id')]),
        ),
    ]
