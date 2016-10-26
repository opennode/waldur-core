# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_enlarge_civil_number_user_field'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='auth_method',
            field=models.CharField(default='default', help_text='Indicates what authentication method were used last time.', max_length=50, verbose_name='authentication method', blank=True),
        ),
    ]
