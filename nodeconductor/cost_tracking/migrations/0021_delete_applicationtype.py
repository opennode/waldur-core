# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cost_tracking', '0020_reset_price_list_item'),
    ]

    operations = [
        migrations.DeleteModel(
            name='ApplicationType',
        ),
    ]
