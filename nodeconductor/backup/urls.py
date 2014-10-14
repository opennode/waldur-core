from django.conf.urls import patterns

from nodeconductor.backup import views


def register_in(router):
    router.register(r'backups', views.BackupViewSet)
    router.register(r'backups-schedules', views.BackupScheduleViewSet)


urlpatterns = patterns(
    '',
)
