from rest_framework import serializers

from nodeconductor.structure import serializers as structure_serializers
from nodeconductor.structure import SupportedServices
from nodeconductor.sugarcrm import models


class ServiceSerializer(structure_serializers.BaseServiceSerializer):

    SERVICE_TYPE = SupportedServices.Types.SugarCRM
    SERVICE_ACCOUNT_FIELDS = {
        'backend_url': 'NodeConductor endpoint (e.g. http://rest-test.nodeconductor.com/)',
        'username': 'NodeConductor user username (e.g. Walter)',
        'password': 'NodeConductor user password (e.g. Walter)',
    }
    SERVICE_ACCOUNT_EXTRA_FIELDS = {
        'backend_spl_id': 'ID of OpenStack service project link that will be used for sugarCRM resources creation. '
                          'Required.',
        'image': 'CRMs OpenStack instance image name. (default: "sugarcrm")',
        'min_cores': 'Minimum amount of cores for CRMs OpenStack instance. (default: 2)',
        'min_ram': 'Minimum amount of ram for CRMs OpenStack instance. (default: 2048 MB)',
        'system_size': 'Storage volume size CRMs OpenStack instance. (default: 32768 MB)',
        'data_size': 'Data volume size of CRMs OpenStack instance. (default: 65536 MB)',
    }

    class Meta(structure_serializers.BaseServiceSerializer.Meta):
        model = models.SugarCRMService
        view_name = 'sugarcrm-detail'


class ServiceProjectLinkSerializer(structure_serializers.BaseServiceProjectLinkSerializer):

    class Meta(structure_serializers.BaseServiceProjectLinkSerializer.Meta):
        model = models.SugarCRMServiceProjectLink
        view_name = 'sugarcrm-spl-detail'
        extra_kwargs = {
            'service': {'lookup_field': 'uuid', 'view_name': 'sugarcrm-detail'},
        }


class CRMSerializer(structure_serializers.BaseResourceSerializer):
    service = serializers.HyperlinkedRelatedField(
        source='service_project_link.service',
        view_name='sugarcrm-detail',
        read_only=True,
        lookup_field='uuid')

    service_project_link = serializers.HyperlinkedRelatedField(
        view_name='sugarcrm-spl-detail',
        queryset=models.SugarCRMServiceProjectLink.objects.all(),
        write_only=True)

    class Meta(structure_serializers.BaseResourceSerializer.Meta):
        model = models.CRM
        view_name = 'sugarcrm-crm-detail'
