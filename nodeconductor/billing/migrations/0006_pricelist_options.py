# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('billing', '0005_payment'),
    ]

    operations = [
        migrations.AddField(
            model_name='pricelist',
            name='options',
            field=jsonfield.fields.JSONField(editable=False, blank=True),
            preserve_default=True,
        ),
    ]
