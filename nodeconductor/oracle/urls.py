from nodeconductor.oracle import views


def register_in(router):
    router.register(r'oracle', views.OracleServiceViewSet, base_name='oracle')
    router.register(r'oracle-zones', views.ZoneViewSet, base_name='oracle-zone')
    router.register(r'oracle-templates', views.TemplateViewSet, base_name='oracle-template')
    router.register(r'oracle-databases', views.DatabaseViewSet, base_name='oracle-database')
    router.register(r'oracle-service-project-link', views.OracleServiceProjectLinkViewSet, base_name='oracle-spl')
