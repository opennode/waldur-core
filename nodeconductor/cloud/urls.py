from django.conf.urls import patterns

from nodeconductor.cloud import views


def register_in(router):
    router.register(r'clouds', views.CloudViewSet)
    router.register(r'flavors', views.FlavorViewSet)
    router.register(r'project-cloud-memberships', views.CloudProjectMembershipViewSet, base_name='cloudproject_membership')
    router.register(r'security-groups', views.SecurityGroupViewSet, base_name='security_group')
    router.register(r'ip-mappings', views.IpMappingViewSet, base_name='ip_mapping')

urlpatterns = patterns(
    '',
)
