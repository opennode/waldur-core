# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


class Migration(migrations.Migration):

    dependencies = [
        ('openstack', '0014_service_and_spl_verbose_name'),
    ]

    operations = [
        migrations.AlterField(
            model_name='flavor',
            name='settings',
            field=models.ForeignKey(related_name='+', to='structure.ServiceSettings'),
            preserve_default=True,
        ),
        migrations.AlterField(
            model_name='image',
            name='settings',
            field=models.ForeignKey(related_name='+', to='structure.ServiceSettings'),
            preserve_default=True,
        ),
        migrations.AlterUniqueTogether(
            name='flavor',
            unique_together=set([('settings', 'backend_id')]),
        ),
        migrations.AlterUniqueTogether(
            name='image',
            unique_together=set([('settings', 'backend_id')]),
        ),
    ]
