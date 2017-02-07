# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0006_user_is_support'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='token_lifetime',
            field=models.PositiveIntegerField(help_text='Token lifetime in seconds.', null=True),
        ),
    ]
