# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('template', '0002_inherit_namemixin'),
    ]

    operations = [
        migrations.RenameField(
            model_name='templateservice',
            old_name='template',
            new_name='base_template',
        ),
        migrations.AlterUniqueTogether(
            name='templateservice',
            unique_together=set([('base_template', 'name', 'polymorphic_ctype')]),
        ),
    ]
