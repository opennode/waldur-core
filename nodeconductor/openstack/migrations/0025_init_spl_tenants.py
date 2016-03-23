# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from uuid import uuid4

from django.db import migrations


OK_STATE = 3


def _get_tenant_name(service_project_link):
    proj = service_project_link.project
    return '%(project_name)s-%(project_uuid)s' % {
        'project_name': ''.join([c for c in proj.name if ord(c) < 128])[:15],
        'project_uuid': proj.uuid.hex[:4]
    }


def create_tenants(apps, schema_editor):
    ServiceProjectLink = apps.get_model('openstack', 'OpenStackServiceProjectLink')
    Tenant = apps.get_model('openstack', 'Tenant')

    for spl in ServiceProjectLink.objects.exclude(tenant_id=''):
        Tenant.objects.create(
            uuid=uuid4().hex,
            name=_get_tenant_name(spl),
            backend_id=spl.tenant_id,
            internal_network_id=spl.internal_network_id,
            external_network_id=spl.external_network_id,
            availability_zone=spl.availability_zone,
            service_project_link=spl,
            state=OK_STATE,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('openstack', '0024_tenant'),
    ]

    operations = [
        migrations.RunPython(create_tenants),
    ]
