from nodeconductor.structure import views as structure_views
from nodeconductor.sugarcrm import models, serializers


class SugarCRMServiceViewSet(structure_views.BaseServiceViewSet):
    queryset = models.SugarCRMService.objects.all()
    serializer_class = serializers.ServiceSerializer


class SugarCRMServiceProjectLinkViewSet(structure_views.BaseServiceProjectLinkViewSet):
    queryset = models.SugarCRMServiceProjectLink.objects.all()
    serializer_class = serializers.ServiceProjectLinkSerializer


class CRMViewSet(structure_views.BaseResourceViewSet):
    queryset = models.CRM.objects.all()
    serializer_class = serializers.CRMSerializer
