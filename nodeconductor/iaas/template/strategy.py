
from nodeconductor.template import TemplateStrategy
from nodeconductor.iaas.models import ServiceTemplate
from nodeconductor.iaas.template.serializers import IaasTemplateSerializer


class IaasTemplateStrategy(TemplateStrategy):

    @classmethod
    def get_model(cls):
        return ServiceTemplate

    @classmethod
    def get_serializer(cls):
        return IaasTemplateSerializer

    @classmethod
    def deploy(cls):
        pass
