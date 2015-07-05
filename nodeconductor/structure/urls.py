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
    router.register(r'services', views.ServiceViewSet, base_name='service')
    router.register(r'resources', views.ResourceViewSet, base_name='resource')
    router.register(r'users', views.UserViewSet)


urlpatterns = patterns(
    '',
    url(r'^stats/creation-time/$', views.CreationTimeStatsView.as_view(), name='stats_creation_time'),
    url(r'^customers/(?P<uuid>[a-z0-9]+)/image/$', views.CustomerImageView.as_view(), name='customer_image'),
)
