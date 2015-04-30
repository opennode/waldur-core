
from nodeconductor.template import TemplateServiceStrategy
from nodeconductor.iaas.models import IaasTemplateService
from nodeconductor.iaas.template.forms import IaasTemplateServiceAdminForm
from nodeconductor.iaas.template.serializers import IaasTemplateServiceSerializer, IaasTemplateServiceCreateSerializer


class IaasTemplateServiceStrategy(TemplateServiceStrategy):

    @classmethod
    def get_model(cls):
        return IaasTemplateService

    @classmethod
    def get_admin_form(cls):
        return IaasTemplateServiceAdminForm

    @classmethod
    def get_serializer(cls):
        return IaasTemplateServiceSerializer

    @classmethod
    def get_create_serializer(cls):
        return IaasTemplateServiceCreateSerializer
