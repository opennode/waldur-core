# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import sorl.thumbnail.fields


class Migration(migrations.Migration):

    dependencies = [
        ('structure', '0011_customer_registration_code'),
    ]

    operations = [
        migrations.AddField(
            model_name='customer',
            name='image',
            field=sorl.thumbnail.fields.ImageField(null=True, upload_to='image', blank=True),
            preserve_default=True,
        ),
    ]
