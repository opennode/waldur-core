# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import datetime
from django.utils.timezone import utc


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_user_registration_method'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='agreement_date',
            field=models.DateTimeField(default=datetime.datetime(2016, 11, 9, 22, 9, 56, 586913, tzinfo=utc), help_text='Indicates when the user has agreed with the policy.', verbose_name='agreement date'),
            preserve_default=False,
        ),
    ]
