# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import nodeconductor.structure.models


def create_service_type(apps, schema_editor):
    service_types = {
        1: 'openstack',
        2: 'digitalocean',
        3: 'aws',
        5: 'gitlab',
        6: 'oracle',
        7: 'azure',
        8: 'nodeconductor_sugarcrm',
        9: 'nodeconductor_saltstack',
        10: 'nodeconductor_zabbix'
    }

    ServiceSettings = apps.get_model('structure', 'ServiceSettings')
    for service in ServiceSettings.objects.all():
        service.service_type = service_types[service.type]
        service.save()


class Migration(migrations.Migration):

    dependencies = [
        ('structure', '0026_add_error_message'),
    ]

    operations = [
        migrations.AddField(
            model_name='servicesettings',
            name='service_type',
            field=models.CharField(max_length=255, default='', db_index=True, validators=[nodeconductor.structure.models.validate_service_type]),
            preserve_default=True,
        ),
        migrations.RunPython(create_service_type),
        migrations.RemoveField(
            model_name='servicesettings',
            name='type',
        ),
        migrations.RenameField(
            model_name='servicesettings',
            old_name='service_type',
            new_name='type'
        ),
        migrations.AlterField(
            model_name='servicesettings',
            name='type',
            field=models.CharField(max_length=255, db_index=True, validators=[nodeconductor.structure.models.validate_service_type]),
            preserve_default=True,
        )
    ]
