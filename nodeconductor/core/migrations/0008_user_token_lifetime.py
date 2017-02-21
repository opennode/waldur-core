# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.core import validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_user_token_lifetime'),
    ]

    operations = [
        migrations.AlterField(
            model_name='user',
            name='token_lifetime',
            field=models.PositiveIntegerField(help_text='Token lifetime in seconds.', null=True,
                                              validators=[validators.MinValueValidator(60)]),
        ),
    ]
