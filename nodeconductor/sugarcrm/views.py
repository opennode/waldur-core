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

    def perform_provision(self, serializer):
        resource = serializer.save()
        backend = resource.get_backend()
        backend.provision(resource)

    # User can only create and delete CRMs. He cannot stop them.
    @structure_views.safe_operation(valid_state=models.CRM.States.ONLINE)
    def destroy(self, request, resource, uuid=None):
        if resource.backend_id:
            backend = resource.get_backend()
            backend.destroy(resource)
        else:
            self.perform_destroy(resource)
