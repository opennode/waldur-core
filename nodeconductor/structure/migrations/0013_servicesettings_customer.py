# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('structure', '0012_customer_image'),
    ]

    operations = [
        migrations.AddField(
            model_name='servicesettings',
            name='customer',
            field=models.ForeignKey(related_name='service_settings', blank=True, to='structure.Customer', null=True),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='service',
            unique_together=set([('customer', 'settings', 'polymorphic_ctype')]),
        ),
    ]
