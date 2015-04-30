# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('template', '0002_inherit_namemixin'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='templateservice',
            unique_together=set([('template', 'name', 'polymorphic_ctype')]),
        ),
    ]
