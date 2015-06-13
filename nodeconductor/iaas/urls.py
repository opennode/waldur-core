from django.conf.urls import patterns, url

from nodeconductor.iaas import views


def register_in(router):
    router.register(r'instances', views.InstanceViewSet)
    router.register(r'iaas-templates', views.TemplateViewSet, base_name='iaastemplate')
    router.register(r'keys', views.SshKeyViewSet)
    router.register(r'template-licenses', views.TemplateLicenseViewSet)
    router.register(r'resources', views.ServiceViewSet, base_name='service')
    # TODO: pending deprecation, use 'resources' instead
    router.register(r'services', views.ServiceViewSet, base_name='service')
    router.register(r'clouds', views.CloudViewSet)
    router.register(r'flavors', views.FlavorViewSet)
    router.register(r'project-cloud-memberships', views.CloudProjectMembershipViewSet, base_name='cloudproject_membership')
    router.register(r'security-groups', views.SecurityGroupViewSet, base_name='security_group')
    router.register(r'ip-mappings', views.IpMappingViewSet, base_name='ip_mapping')
    router.register(r'floating-ips', views.FloatingIPViewSet, base_name='floating_ip')

urlpatterns = patterns(
    '',
    url(r'^stats/customer/$', views.CustomerStatsView.as_view(), name='stats_customer'),
    url(r'^stats/usage/$', views.UsageStatsView.as_view(), name='stats_usage'),
    url(r'^stats/resource/$', views.ResourceStatsView.as_view(), name='stats_resource'),
    url(r'^stats/quota/$', views.QuotaStatsView.as_view(), name='stats_quota'),
    url(r'^stats/quota/timeline/$', views.QuotaTimelineStatsView.as_view(), name='stats_quota_timeline'),
    url(r'^stats/alerts/$', views.OpenstackAlertStatsView.as_view(), name='stats_alerts'),
)
