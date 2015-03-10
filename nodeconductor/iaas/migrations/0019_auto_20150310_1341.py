# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('iaas', '0018_remove_old_quotas'),
    ]

    operations = [
        migrations.AlterField(
            model_name='iaastemplateservice',
            name='service',
            field=models.ForeignKey(related_name='+', on_delete=django.db.models.deletion.SET_NULL, blank=True, to='iaas.Cloud', null=True),
            preserve_default=True,
        ),
    ]
