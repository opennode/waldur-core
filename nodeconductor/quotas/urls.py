from django.conf.urls import url
from nodeconductor.quotas import views


def register_in(router):
    router.register(r'quotas', views.QuotaViewSet)

urlpatterns = (
    url(r'^stats/quota/timeline/$', views.QuotaTimelineStatsView.as_view(), name='stats_quota_timeline'),
)