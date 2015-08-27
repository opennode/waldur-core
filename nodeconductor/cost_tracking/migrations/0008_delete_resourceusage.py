# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('cost_tracking', '0007_remove_obsolete_billing_fields'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='resourceusage',
            unique_together=None,
        ),
        migrations.RemoveField(
            model_name='resourceusage',
            name='content_type',
        ),
        migrations.DeleteModel(
            name='ResourceUsage',
        ),
        migrations.AlterField(
            model_name='defaultpricelistitem',
            name='value',
            field=models.DecimalField(default=0, verbose_name=b'Hourly rate', max_digits=9, decimal_places=2),
            preserve_default=True,
        ),
    ]
