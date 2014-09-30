from __future__ import unicode_literals

from django.conf.urls import patterns

from nodeconductor.structure import views


def register_in(router):
    router.register(r'customers', views.CustomerViewSet)
    router.register(r'projects', views.ProjectViewSet)
    router.register(r'project-groups', views.ProjectGroupViewSet)
    router.register(r'project-group-memberships', views.ProjectGroupMembershipViewSet,
                    base_name='projectgroup_membership')
    router.register(r'customer-permissions', views.CustomerPermissionViewSet, base_name='customer_permission')
    router.register(r'project-permissions', views.ProjectPermissionViewSet, base_name='project_permission')
    router.register(r'users', views.UserViewSet)


urlpatterns = patterns(
    '',
)
