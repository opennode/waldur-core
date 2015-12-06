# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import nodeconductor.structure.models


def create_service_type(apps, schema_editor):
    service_types = {
        1: 'OpenStack',
        2: 'DigitalOcean',
        3: 'Amazon',
        5: 'GitLab',
        6: 'Oracle',
        7: 'Azure',
        8: 'SugarCRM',
        9: 'SaltStack',
        10: 'Zabbix'
    }

    ServiceSettings = apps.get_model('structure', 'ServiceSettings')
    for service in ServiceSettings.objects.all():
        try:
            service.service_type = service_types[service.type]
            service.save()
        except KeyError:
            pass


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
