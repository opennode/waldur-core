from __future__ import unicode_literals

from django.conf.urls import patterns, url

from nodeconductor.structure import views


def register_in(router):
    router.register(r'customers', views.CustomerViewSet)
    router.register(r'projects', views.ProjectViewSet)
    router.register(r'project-groups', views.ProjectGroupViewSet)
    router.register(r'project-group-memberships', views.ProjectGroupMembershipViewSet,
                    base_name='projectgroup_membership')
    router.register(r'customer-permissions', views.CustomerPermissionViewSet, base_name='customer_permission')
    router.register(r'project-permissions', views.ProjectPermissionViewSet, base_name='project_permission')
    router.register(r'project-group-permissions', views.ProjectGroupPermissionViewSet, base_name='projectgroup_permission')
    router.register(r'service-settings', views.ServiceSettingsViewSet)
    router.register(r'service-metadata', views.ServiceMetadataViewSet, base_name='service_metadata')
    router.register(r'services', views.ServicesViewSet, base_name='service_items')
    router.register(r'resources', views.ResourceViewSet, base_name='resource')
    router.register(r'users', views.UserViewSet)
    router.register(r'keys', views.SshKeyViewSet)


urlpatterns = patterns(
    '',
    url(r'^stats/creation-time/$', views.CreationTimeStatsView.as_view(), name='stats_creation_time'),
    url(r'^stats/quota/$', views.AggregatedStatsView.as_view(), name='stats_quota'),
    url(r'^stats/quota/timeline/$', views.QuotaTimelineStatsView.as_view(), name='stats_quota_timeline'),
    url(r'^customers/(?P<uuid>[a-z0-9]+)/image/$', views.CustomerImageView.as_view(), name='customer_image'),
    url(r'^customers/(?P<uuid>[a-z0-9]+)/counters/$', views.CustomerCountersView.as_view({'get': 'list'}), name='customer_counters'),
    url(r'^projects/(?P<uuid>[a-z0-9]+)/counters/$', views.ProjectCountersView.as_view({'get': 'list'}), name='project_counters'),
    url(r'^user-counters/$', views.UserCountersView.as_view({'get': 'list'}), name='user_counters'),
)
