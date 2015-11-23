from nodeconductor.template import views


def register_in(router):
    router.register(r'template-groups', views.TemplateGroupViewSet, base_name='template-group')
    router.register(r'template-results', views.TemplateGroupResultViewSet, base_name='template-result')
