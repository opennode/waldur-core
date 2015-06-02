from nodeconductor.oracle import views


def register_in(router):
    router.register(r'oracle', views.ServiceViewSet, base_name='oracle')
    router.register(r'oracle-zones', views.ZoneViewSet, base_name='oracle-zone')
    router.register(r'oracle-templates', views.TemplateViewSet, base_name='oracle-template')
    router.register(r'oracle-service-project-link', views.ServiceProjectLinkViewSet, base_name='oracle-spl')
