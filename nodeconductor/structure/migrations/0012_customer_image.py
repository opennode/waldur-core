# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import nodeconductor.structure.images


class Migration(migrations.Migration):

    dependencies = [
        ('structure', '0011_customer_registration_code'),
    ]

    operations = [
        migrations.AddField(
            model_name='customer',
            name='image',
            field=models.ImageField(null=True, upload_to=nodeconductor.structure.images.get_upload_path, blank=True),
            preserve_default=True,
        ),
    ]
