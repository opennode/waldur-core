# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('iaas', '0054_delete_iaastemplate'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='cloud',
            name='dummy',
        ),
    ]
