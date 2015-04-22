from django.conf.urls import patterns

from nodeconductor.jira import views


def register_in(router):
    router.register(r'tickets', views.TicketViewSet, base_name='ticket')


urlpatterns = patterns(
    '',
)
