from . import views


def register_in(router):
    router.register(r'monitoring-events', views.ResourceStateViewSet, base_name='monitoring-event')
