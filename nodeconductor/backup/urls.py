from django.conf.urls import patterns

from nodeconductor.backup import views


def register_in(router):
    router.register(r'backups', views.BackupViewSet)
    router.register(r'backup-schedules', views.BackupScheduleViewSet)


urlpatterns = patterns(
    '',
)
