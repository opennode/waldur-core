# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations


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
        ('structure', '0027_servicesettings_service_type'),
    ]

    operations = [
        migrations.RunPython(create_service_type)
    ]
