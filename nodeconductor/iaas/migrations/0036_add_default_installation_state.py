# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('iaas', '0035_add_list_of_application_types'),
    ]

    operations = [
        migrations.AlterField(
            model_name='instance',
            name='installation_state',
            field=models.CharField(default='NO DATA', help_text='State of post deploy installation process', max_length=50, blank=True),
            preserve_default=True,
        ),
    ]
