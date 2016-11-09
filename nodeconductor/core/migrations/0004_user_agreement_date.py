# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_user_registration_method'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='agreement_date',
            field=models.DateTimeField(default=django.utils.timezone.now, help_text='Indicates when the user has agreed with the policy.', verbose_name='agreement date'),
        ),
    ]
