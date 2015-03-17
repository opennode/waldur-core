from nodeconductor.quotas import views


def register_in(router):
    router.register(r'quotas', views.QuotaViewSet)
