# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from keystoneclient.exceptions import ClientException
from neutronclient.common.exceptions import NeutronClientException

from nodeconductor.iaas.backend import OpenStackBackend


def get_tenant_name(membership):
    return '{0}-{1}'.format(membership.project.uuid.hex, membership.project.name)


def populate_internal_network(apps, schema_editor):
    # check if such a network already exists, if so -- use it instead
    CloudProjectMembership = apps.get_model("iaas", "CloudProjectMembership")
    db_alias = schema_editor.connection.alias

    openstack = OpenStackBackend()
    for cpm in CloudProjectMembership.objects.using(db_alias).filter(internal_network_id='').iterator():
        network_name = get_tenant_name(cpm)
        network_lookup = {
            'name': network_name,
            'tenant_id': cpm.tenant_id,
        }
        try:
            session = openstack.create_tenant_session(cpm)
            neutron = openstack.create_neutron_client(session)

            networks_by_name = neutron.list_networks(**network_lookup)['networks']
            network_id = networks_by_name[0]['id']
        except (ClientException, NeutronClientException, KeyError):
            network_id = 'ERROR-API'
        except IndexError:
            network_id = 'ERROR-NOT-FOUND'
        else:
            if len(networks_by_name) > 1:
                network_id = 'ERROR-TOO-MANY'

        cpm.internal_network_id = network_id
        cpm.save()


class Migration(migrations.Migration):

    dependencies = [
        ('iaas', '0014_servicestatistics'),
    ]

    operations = [
        migrations.AddField(
            model_name='cloudprojectmembership',
            name='internal_network_id',
            field=models.CharField(max_length=64, blank=True, default=''),
            preserve_default=False,
        ),
        migrations.RunPython(
            populate_internal_network,
        ),
    ]
