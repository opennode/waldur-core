# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('iaas', '0033_add_validator_to_instance_user_data'),
    ]

    operations = [
        migrations.AddField(
            model_name='instance',
            name='installation_state',
            field=models.CharField(help_text='State of post deploy installation process', max_length=50, blank=True),
            preserve_default=True,
        ),
    ]
