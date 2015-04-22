from __future__ import unicode_literals

from django.conf import settings
from django.conf.urls import patterns
from django.conf.urls import include
from django.conf.urls import url
from django.contrib import admin
from django.views.generic import TemplateView
import permission

from nodeconductor.core.routers import SortedDefaultRouter as DefaultRouter
from nodeconductor.backup import urls as backup_urls
from nodeconductor.iaas import urls as iaas_urls
from nodeconductor.jira import urls as jira_urls
from nodeconductor.structure import urls as structure_urls
from nodeconductor.template import urls as template_urls
from nodeconductor.quotas import urls as quotas_urls


admin.autodiscover()
permission.autodiscover()

router = DefaultRouter()
iaas_urls.register_in(router)
structure_urls.register_in(router)
template_urls.register_in(router)
backup_urls.register_in(router)
quotas_urls.register_in(router)
jira_urls.register_in(router)


urlpatterns = patterns(
    '',
    url(r'^admin/', include(admin.site.urls), name='admin'),
    url(r'^api/', include(router.urls)),
    url(r'^api/', include('nodeconductor.events.urls')),
    url(r'^api/', include('nodeconductor.iaas.urls')),
    url(r'^api/', include('nodeconductor.structure.urls')),
    url(r'^api/version/', 'nodeconductor.core.views.version_detail'),
    url(r'^api-auth/password/', 'nodeconductor.core.views.obtain_auth_token'),
    url(r'^api-auth/saml2/', 'nodeconductor.core.views.assertion_consumer_service'),
    url(r'^api-auth/', include('rest_framework.urls',
                               namespace='rest_framework')),
    url(r'^$', TemplateView.as_view(template_name='landing/index.html')),
)


if settings.DEBUG:
    (r'^%{static_url}/(?P<path>.*)$'.format(static_url=settings.STATIC_URL),
        'django.views.static.serve', {'document_root': settings.STATIC_ROOT}),
