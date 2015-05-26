# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('template', '0003_rename_tamplate_field'),
    ]

    operations = [
        migrations.AlterField(
            model_name='templateservice',
            name='polymorphic_ctype',
            field=models.ForeignKey(related_name='polymorphic_template.templateservice_set+', editable=False, to='contenttypes.ContentType', null=True),
            preserve_default=True,
        ),
    ]
